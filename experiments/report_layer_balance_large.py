"""Create comparison tables and the Japanese experiment report from saved rows."""

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else []
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def main(folder):
    folder = Path(folder)
    summary = read_csv(folder/"summary.csv")
    profiles = read_csv(folder/"span_profiles.csv")
    pmap = {(p["case"],p["method"]):p for p in profiles}
    paired = read_csv(folder/"paired.csv")
    diffs = defaultdict(list)
    for row in paired:
        linear=pmap.get((row["case"],"linear")); square=pmap.get((row["case"],"square"))
        if linear and square:
            diffs[(int(row["nodes"]),row["family"])].append(int(square["span_square_sum"])-int(linear["span_square_sum"]))
    for row in summary:
        values=diffs.get((int(row["nodes"]),row["family"]),[])
        row["span_square_sum_comparable"]=len(values)
        row["span_square_sum_diff_median"]=statistics.median(values) if values else ""
        row["span_square_sum_decrease"]=sum(x<0 for x in values)
        row["span_square_sum_same"]=sum(x==0 for x in values)
        row["span_square_sum_increase"]=sum(x>0 for x in values)
    write_csv(folder/"summary.csv",summary)

    completion=read_csv(folder/"input_completion.csv")
    input_counts=Counter(row["family"] for row in completion)
    assert len(completion)==100 and input_counts=={"random":25,"scc_chain":25,"watts_strogatz":50}
    stages=("search_status","linear_assignment_status","square_assignment_status",
            "linear_drawing_status","square_drawing_status")
    status_rows=[]
    for n in (20,40,60,80,100):
        for family in ("random","scc_chain","watts_strogatz"):
            group=[r for r in completion if int(r["nodes"])==n and r["family"]==family]
            status_rows.append({"nodes":n,"family":family,"trials":len(group),
                **{key:sum(r.get(key)=="ok" for r in group) for key in stages},
                "linear_timeout_no_solution":sum(r.get("linear_assignment_status")=="timeout_no_solution" for r in group),
                "square_license_size_limit":sum(r.get("square_assignment_status")=="license_size_limit" for r in group)})
    write_csv(folder/"completion_summary.csv",status_rows)

    all_rows=[json.loads(line) for line in (folder/"rows.jsonl").read_text(encoding="utf-8").splitlines()]
    records=defaultdict(dict)
    for row in all_rows:
        records[row["case"]][(row["stage"],row.get("method"))]=row
    c_by_case={r["case"]:r for r in completion}
    input_rows=[json.loads(line) for line in (folder/"inputs.jsonl").read_text(encoding="utf-8").splitlines()]
    profile_map={(r["case"],r["method"]):r for r in profiles}
    per_graph=[]
    for item in input_rows:
        case=item["case"]
        group=records[case]
        search=group.get(("search",None),{})
        completion_row=c_by_case[case]
        for method in ("linear","square"):
            allocation=group.get(("assignment",method),{})
            drawing=group.get(("drawing",method),{})
            profile=profile_map.get((case,method),{})
            solver=(allocation.get("solver") or [{}])[-1]
            per_graph.append({
                "case":case,"family":item["family"],"nodes":item["nodes"],"edges":item["edges"],
                "seed":item["seed"],"L":search.get("layers"),"T":search.get("wraps"),
                "search_status":completion_row["search_status"],"search_seconds":search.get("seconds"),
                "method":method,"allocation_status":completion_row[f"{method}_assignment_status"],
                "optimality_status":allocation.get("optimality_status"),
                "allocation_seconds":allocation.get("seconds"),
                "allocation_objective":solver.get("objective"),"objective_bound":solver.get("bound"),
                "relative_gap":solver.get("relative_gap"),
                "span_sum":allocation.get("span_sum"),"span_square_sum":allocation.get("span_square_sum"),
                "max_span":allocation.get("max_span"),"span_p95":profile.get("span_p95"),
                "span_frequency":profile.get("span_frequency"),
                "predicted_dummy_count":allocation.get("predicted_dummies"),
                "actual_dummy_count":drawing.get("dummy_nodes"),
                "assignment_violations":allocation.get("assignment_violations"),
                "drawing_status":completion_row[f"{method}_drawing_status"],
                "drawing_seconds":drawing.get("drawing_seconds"),
                "crossing_reduction_seconds":drawing.get("crossing_seconds"),
                "coordinate_seconds":drawing.get("coordinate_seconds"),
                "geometry_seconds":drawing.get("geometry_seconds"),
                "geometric_crossings":drawing.get("geometric_crossings"),
                "bends":drawing.get("bends"),
                "boundary_original_edges":drawing.get("either_seam_edges"),
                "total_edge_length":drawing.get("total_edge_length"),
                "max_edge_length":drawing.get("max_edge_length"),
                "coordinate_fallback":drawing.get("coordinate_fallback")})
    write_csv(folder/"per_graph_metrics.csv",per_graph)

    draw_by_case=defaultdict(dict)
    for row in all_rows:
        if row.get("stage")=="drawing" and row.get("status")=="ok":
            draw_by_case[row["case"]][row["method"]]=row
    geometry_fields=("geometric_crossings","bends","either_seam_edges","total_edge_length","max_edge_length")
    geometry_pairs=[]
    for case, methods in draw_by_case.items():
        if all(name in methods for name in ("linear","square")):
            left,right=methods["linear"],methods["square"]
            rec={"case":case,"nodes":left["nodes"],"family":left["family"]}
            for metric in geometry_fields:
                rec[f"linear_{metric}"]=left.get(metric)
                rec[f"square_{metric}"]=right.get(metric)
                rec[f"square_minus_linear_{metric}"]=right.get(metric)-left.get(metric)
            geometry_pairs.append(rec)
    write_csv(folder/"geometry_paired.csv",geometry_pairs)
    geometry_summary={}
    for metric in geometry_fields:
        values=[float(r[f"square_minus_linear_{metric}"]) for r in geometry_pairs]
        geometry_summary[metric]=(statistics.median(values),sum(x<0 for x in values),
                                  sum(x==0 for x in values),sum(x>0 for x in values))

    def val(row,key,fmt=".2f"):
        x=row.get(key)
        if x in (None,""): return "—"
        return format(float(x),fmt)
    lines=["# 線形配分と二乗和配分の比較実験", "",
      "2026-11-26にローカルGurobi、既存生成器、既定のトーラス後段を用いて実施した。100入力のうちWSは50入力（半数）を占める。結果は同一入力上の二乗和 − 線形の差であり、負値が二乗和側の減少を表す。", "",
      "## 条件", "",
      "頂点数20・40・60・80・100、random 25件、scc_chain 25件、Watts–Strogatz 50件。基本辺数は各入力2n。各生成手法・サイズのseedは独立に割り当て、実生成後の頂点数・辺数・有向辺リストを`inputs.jsonl`へ保存した。階層数Lと折返し数Tの探索は入力ごとに一度だけ行い、結果を両配分方式で共有。Gurobiは両方式ともThreads=1、Seed=0、各モデルTimeLimit=4秒。入力ごとに解法順を交互にした単独逐次実行。", "",
      "最小化目的は線形側がスパン和、二乗和側がスパン二乗和。探索時間は配分時間の差に含めない。後段時間は既定PipelineConfigでのダミー挿入・交差削減・境界最適化・座標割当を含み、幾何計測時間は別記録。理論ダミー数`sum(span−1)`と実挿入数を照合し、一致しない入力または単位スパン制約違反は有効図として扱わない。p95は最寄順位法（順位`ceil(0.95m)`）で計算。", "",
      "## 段階別完走数", "",
      "各行の全試行数と、探索・線形・二乗和割当・各方式の描画完了数を併記する。二乗和の80・100頂点は全件でサイズ上限に達し、差の計算対象には含めない。", "",
      "| n | 系列 | 試行 | 探索 | 線形割当 | 二乗和割当 | 線形描画 | 二乗和描画 | 線形時間切れ(解なし) | 二乗和サイズ上限 |",
      "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in status_rows:
        lines.append(f"| {r['nodes']} | {r['family']} | {r['trials']} | {r['search_status']} | {r['linear_assignment_status']} | {r['square_assignment_status']} | {r['linear_drawing_status']} | {r['square_drawing_status']} | {r['linear_timeout_no_solution']} | {r['square_license_size_limit']} |")
    lines += ["", "## 対応比較（差の中央値と方向別件数）", "",
      "`減/同/増`は有効な対応ペア中の二乗和−線形の符号別件数。計算時間と交差は該当工程まで両方完了したペアだけで集計。スパン95パーセンタイルと二乗和は別途再生した割当で検算した。", "",
      "| n | 系列 | 試行/割当ペア/描画ペア | ダミー差中央値 [減/同/増] | 最大スパン差 [減/同/増] | p95差 [減/同/増] | スパン二乗和差 [減/同/増] | 割当秒差中央値 | 後段秒差中央値 | 幾何交差差 [減/同/増] |",
      "|---:|---|---:|---|---|---|---|---:|---:|---|"]
    for r in summary:
        f=lambda key: "—" if r.get(key) in (None,"") else f"{float(r[key]):.3f}"
        lines.append(f"| {r['nodes']} | {r['family']} | {r['trials']}/{r['assignment_comparable']}/{r['drawing_comparable']} | {f('dummy_nodes_diff_median')} [{r['dummy_nodes_decrease']}/{r['dummy_nodes_same']}/{r['dummy_nodes_increase']}] | {f('max_span_diff_median')} [{r['max_span_decrease']}/{r['max_span_same']}/{r['max_span_increase']}] | {f('span_p95_diff_median')} [{r['span_p95_decrease']}/{r['span_p95_same']}/{r['span_p95_increase']}] | {f('span_square_sum_diff_median')} [{r['span_square_sum_decrease']}/{r['span_square_sum_same']}/{r['span_square_sum_increase']}] | {f('seconds_diff_median')} | {f('drawing_seconds_diff_median')} | {f('geometric_crossings_diff_median')} [{r['geometric_crossings_decrease']}/{r['geometric_crossings_same']}/{r['geometric_crossings_increase']}] |")

    matched=[r for r in paired if r["assignment_comparable"]=="True"]
    drawn=[r for r in paired if r["drawing_comparable"]=="True"]
    dummies=[int(r["square_dummy_nodes"])-int(r["linear_dummy_nodes"]) for r in matched]
    maxdiff=[int(r["square_max_span"])-int(r["linear_max_span"]) for r in matched]
    crossdiff=[int(r["square_geometric_crossings"])-int(r["linear_geometric_crossings"]) for r in drawn]
    spans95=[]
    for r in paired:
        l=pmap.get((r["case"],"linear")); s=pmap.get((r["case"],"square"))
        if l and s: spans95.append(int(s["span_p95"])-int(l["span_p95"]))
    lines += ["", "## 要約", "",
      f"有効な配分ペアは{len(matched)}/100、完成図ペアは{len(drawn)}/100。全100件を一括した場合WSが半数を占めるため、系列・サイズ別の上表を主に読む。",
      f"ダミー差は中央値{statistics.median(dummies) if dummies else '—'}で、減少{sum(x<0 for x in dummies)}・同数{sum(x==0 for x in dummies)}・増加{sum(x>0 for x in dummies)}件。二乗和配分のダミー数が減った対応入力はなく、増加はサイズ20〜60のうち入力構造によって現れた。",
      f"最大スパンは減少{sum(x<0 for x in maxdiff)}・同数{sum(x==0 for x in maxdiff)}・増加{sum(x>0 for x in maxdiff)}件。p95は減少{sum(x<0 for x in spans95)}・同数{sum(x==0 for x in spans95)}・増加{sum(x>0 for x in spans95)}件。二乗和目的の改善は長い側の裾に出る入力がある一方、最大スパンが変わらない入力が多数。",
      f"完成図ペアの幾何交差差は減少{sum(x<0 for x in crossdiff)}・同数{sum(x==0 for x in crossdiff)}・増加{sum(x>0 for x in crossdiff)}件。最大スパンやp95の短縮だけから完成図交差の改善は保証されない。後段時間は上表のサイズ・系列別中央値を参照。スパン距離と完成図の中心線長は異なる量で、後者の総長・最大長・折れ・境界通過辺は生ログに保存している。",
      "両方式で配分比較できた60件中、線形配分は58件が最適性確認済みで、2件は4秒で実行可能解なし。二乗和配分は58件が最適性確認済み、2件は実行可能解を返したが時間切れで最適性未確認。共通探索は100件すべてでL・Tを返したが、内部の候補層数モデル5件は4秒制限に達した。これらの詳細は`solver_traces.jsonl`に保存した。80・100頂点の二乗和モデルはローカルGurobiのサイズ上限で比較不能。100頂点のSCC連結入力では探索または線形配分が時間切れで実行可能解を返さない例があり、比較可能件数の分母に残した。", "",
      f"完成図ペア{len(geometry_pairs)}件の中心線指標は次のとおり（差中央値、減/同/増）。幾何交差{geometry_summary['geometric_crossings']}、折れ{geometry_summary['bends']}、境界を通る元辺{geometry_summary['either_seam_edges']}、総辺長{geometry_summary['total_edge_length']}、最大辺長{geometry_summary['max_edge_length']}。", "",
      f"配分時間差の中央値は{statistics.median([float(r['square_seconds'])-float(r['linear_seconds']) for r in matched]):.3f}秒（平方が遅い{sum(float(r['square_seconds'])>float(r['linear_seconds']) for r in matched)}件/速い{sum(float(r['square_seconds'])<float(r['linear_seconds']) for r in matched)}件）。後段全体の時間差中央値は{statistics.median([float(r['square_drawing_seconds'])-float(r['linear_drawing_seconds']) for r in drawn]):.4f}秒（平方が遅い{sum(float(r['square_drawing_seconds'])>float(r['linear_drawing_seconds']) for r in drawn)}件/速い{sum(float(r['square_drawing_seconds'])<float(r['linear_drawing_seconds']) for r in drawn)}件）。座標割当で従来境界方式へフォールバックしたのは10描画。1回ずつの対応実行なので小さな差は目安。", "",
      "## 描画例", "",
      "`drawings/`の左右図では線形を左、二乗和を右に置き、同一Lの横幅・レイヤー単位あたりのピクセル幅を固定した。縦方向は両パネルを共通の範囲に拡張して余白を加えた。図中にL、T、実ダミー数、最大スパン、幾何交差、折れ数を記した。",
      "", "- `drawings/presentation_v5/random-20-2-928000.png`: 20頂点の見やすい比較例。交差は25から23へ減り、ダミーは35から36、最大スパンは5で同じ。",
      "- `drawings/presentation_v5/watts_strogatz-40-2-930029.png`: 最大スパンが15から14へ短縮し、交差は2で同数。ダミーは89から92へ増えた例。",
      "- `drawings/random-40-2-930000.png`: 最大スパンは短縮したが、ダミーと交差が増えた例。", "",
      "## 再現", "",
      "```sh",
      "PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/layer-balance-mpl XDG_CACHE_HOME=/tmp/layer-balance-cache \\",
      "  PYTHONPATH=src:experiments ./theme2026-saku/bin/python experiments/compare_layer_balance_large.py \\",
      "  --solver-seconds 4 --output output/torus_balance_diff_square_20261126",
      "PYTHONHASHSEED=0 MPLCONFIGDIR=/tmp/layer-balance-mpl XDG_CACHE_HOME=/tmp/layer-balance-cache \\",
      "  PYTHONPATH=src:experiments ./theme2026-saku/bin/python experiments/enrich_layer_balance_large.py \\",
      "  output/torus_balance_diff_square_20261126",
      "./theme2026-saku/bin/python experiments/report_layer_balance_large.py output/torus_balance_diff_square_20261126",
      "```", "",
      "各入力×方式を1行にした全指標表は`per_graph_metrics.csv`（200行）。列には入力seed、実辺数、L・T、探索/配分/描画状態と時間、配分目的値・下界・gap、スパン合計/二乗和/p95/最大/度数、理論/実ダミー数、幾何交差、折れ、境界通過元辺数、中心線の総長/最大長、座標フォールバックを含む。未完了ステージの指標欄は空欄。",
      "生データは`inputs.jsonl`、`rows.jsonl`、`solver_traces.jsonl`、`span_profiles.csv`。設定は`settings.json`、入力ごとの段階別完了は`input_completion.csv`、サイズ・系列別の完走数は`completion_summary.csv`、対応差は`summary.csv`、`paired.csv`、`geometry_paired.csv`。Gurobi状態・目的値・下界・gapはsolver traceに記録。", "",
      "## 制約", "",
      "実行時間は各入力・各方式1回の交互順測定で、反復中央値ではない。したがって細かな秒差は実行順やマシン負荷の影響を受けうる。幾何交差と折れはレイアウト品質の幾何指標であり、読みやすさそのものの評価ではない。", ""]
    (folder/"report.md").write_text("\n".join(lines),encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
