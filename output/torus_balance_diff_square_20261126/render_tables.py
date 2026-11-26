#!/usr/bin/env python3
"""Render the experiment CSV outputs as a browsable Japanese HTML report."""
from csv import DictReader
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "comparison_tables.html"
FIG = ROOT / "drawings" / "presentation_v5"

def rows(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as f:
        return list(DictReader(f))

def table(data, columns, table_id, numeric=()):
    head = "".join(f'<th>{escape(label)}</th>' for _, label in columns)
    body = []
    for row in data:
        cells = []
        for key, label in columns:
            value = row.get(key, "")
            if key == "span_frequency" and value:
                value = value.replace('"', "'")
            cls = "num" if key in numeric else ""
            cells.append(f'<td class="{cls}">{escape(str(value))}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="table-wrap"><table id="{table_id}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

summary = rows("summary.csv")
detail = rows("per_graph_metrics.csv")
completion = rows("input_completion.csv")
summary_columns = [
    ("nodes","頂点数"),("family","生成系列"),("trials","試行数"),
    ("assignment_comparable","割当比較 n"),("drawing_comparable","描画比較 n"),
    ("dummy_nodes_diff_median","ダミー数 Δ 中央値"),("dummy_nodes_decrease","減少"),("dummy_nodes_same","同数"),("dummy_nodes_increase","増加"),
    ("max_span_diff_median","最大スパン Δ 中央値"),("max_span_decrease","減少"),("max_span_same","同数"),("max_span_increase","増加"),
    ("span_p95_diff_median","p95 Δ 中央値"),("span_p95_decrease","減少"),("span_p95_same","同数"),("span_p95_increase","増加"),
    ("span_square_sum_diff_median","スパン二乗和 Δ 中央値"),("span_square_sum_decrease","減少"),("span_square_sum_same","同数"),("span_square_sum_increase","増加"),
    ("seconds_diff_median","配分秒 Δ 中央値"),("seconds_decrease","速い"),("seconds_same","同じ"),("seconds_increase","遅い"),
    ("drawing_seconds_diff_median","後段秒 Δ 中央値"),("drawing_seconds_decrease","速い"),("drawing_seconds_same","同じ"),("drawing_seconds_increase","遅い"),
    ("geometric_crossings_diff_median","幾何交差 Δ 中央値"),("geometric_crossings_decrease","減少"),("geometric_crossings_same","同数"),("geometric_crossings_increase","増加")]
detail_columns = [
    ("case","入力ID"),("family","系列"),("nodes","頂点"),("edges","辺"),("seed","乱数種"),("method","方式"),("L","L"),("T","T"),
    ("search_status","探索状態"),("search_seconds","探索秒"),("allocation_status","割当状態"),("optimality_status","最適性"),("allocation_seconds","配分秒"),
    ("allocation_objective","目的値"),("objective_bound","下界"),("relative_gap","ギャップ"),("span_sum","総スパン"),("span_square_sum","スパン二乗和"),("max_span","最大スパン"),("span_p95","p95"),("span_frequency","スパン度数"),
    ("predicted_dummy_count","理論ダミー数"),("actual_dummy_count","実ダミー数"),("assignment_violations","割当違反"),("drawing_status","描画状態"),("drawing_seconds","後段秒"),("crossing_reduction_seconds","交差削減秒"),("coordinate_seconds","座標秒"),("geometry_seconds","幾何計測秒"),
    ("geometric_crossings","幾何交差数"),("bends","折れ数"),("boundary_original_edges","境界通過元辺数"),("total_edge_length","中心線総延長"),("max_edge_length","中心線最大長"),("coordinate_fallback","座標フォールバック")]
completion_columns = [("case","入力ID"),("family","系列"),("nodes","頂点"),("edges","実辺数"),("seed","乱数種"),("search_status","探索"),("layers","L"),("wraps","T"),("linear_assignment_status","線形割当"),("linear_assignment_solver_status","線形ソルバー"),("linear_assignment_objective","線形目的値"),("linear_assignment_bound","線形下界"),("linear_assignment_gap","線形ギャップ"),("square_assignment_status","二乗和割当"),("square_assignment_solver_status","二乗和ソルバー"),("square_assignment_objective","二乗和目的値"),("square_assignment_bound","二乗和下界"),("square_assignment_gap","二乗和ギャップ"),("linear_drawing_status","線形描画"),("linear_drawing_fallback","線形フォールバック"),("square_drawing_status","二乗和描画"),("square_drawing_fallback","二乗和フォールバック")]

parts = ["""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>線形配分と二乗和配分｜実験結果</title>
<style>
:root{font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN",Meiryo,sans-serif;color:#182334;background:#f5f7fa}body{margin:0}header{background:#17365d;color:#fff;padding:28px max(24px,calc((100vw - 1500px)/2))}h1{margin:0 0 8px;font-size:26px}header p{margin:0;color:#dce8f5}.container{max-width:1500px;margin:auto;padding:24px}section{background:#fff;border:1px solid #dce3eb;border-radius:12px;padding:20px;margin:0 0 22px;box-shadow:0 2px 8px #20344a0b}h2{font-size:20px;margin:0 0 10px;color:#17365d}h3{margin:18px 0 8px}.note{font-size:13px;color:#536273}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}.kpi{background:#eef4fa;border-radius:9px;padding:12px}.kpi b{display:block;font-size:23px;color:#17365d}.kpi span{font-size:12px;color:#536273}.table-wrap{overflow:auto;max-height:70vh;border:1px solid #e0e6ed;border-radius:8px}table{border-collapse:separate;border-spacing:0;white-space:nowrap;font-size:12px;width:max-content;min-width:100%}th,td{padding:7px 9px;border-bottom:1px solid #e7ebf0;border-right:1px solid #edf0f3;text-align:left}th{position:sticky;top:0;background:#17365d;color:#fff;z-index:1}tbody tr:nth-child(even){background:#f7f9fb}td.num{text-align:right;font-variant-numeric:tabular-nums}img{max-width:100%;height:auto;border:1px solid #dce3eb;border-radius:8px}figure{margin:14px 0}figcaption{font-size:13px;color:#536273;margin-top:6px}input{padding:9px 12px;border:1px solid #bbc8d5;border-radius:8px;width:min(460px,90%);font:inherit}.tag{display:inline-block;background:#e7eff8;color:#17365d;border-radius:99px;padding:3px 8px;font-size:12px;margin-right:5px}a{color:#1765a5}footer{color:#667587;font-size:12px;padding:10px 0 30px}
</style><header><h1>線形配分と二乗和配分｜比較実験</h1><p>サイズ・生成系列別の集計と、入力×方式ごとの全指標を収録</p></header><main class="container">"""]
parts.append(f'<section><h2>全体像</h2><p class="note">全100入力・5サイズ。ランダム有向グラフ25件、小さいSCC連結25件、WS 50件（全体の半数）。差分は二乗和 − 線形で、負値は二乗和側で小さい値です。</p><div class="kpis"><div class="kpi"><b>{len(completion)}</b><span>入力総数</span></div><div class="kpi"><b>{sum(int(r["assignment_comparable"]) for r in summary)}</b><span>割当比較可能ペア</span></div><div class="kpi"><b>{sum(int(r["drawing_comparable"]) for r in summary)}</b><span>描画比較可能ペア</span></div><div class="kpi"><b>{sum(1 for r in detail if r["coordinate_fallback"]=="True")}</b><span>座標フォールバック（方式×入力）</span></div></div><p class="note">比較件数はサイズ×系列ごとに異なります。表中の n を参照してください。100頂点では二乗和割当のサイズ上限による未完了行も完走表に残しています。</p></section>')
parts.append('<section><h2>サイズ・系列別サマリー</h2><p class="note">中央値と増減件数を指標別に確認できます。配分・後段時間の「速い／遅い」も差分（二乗和 − 線形）で判定しています。</p>')
parts.append(table(summary,summary_columns,'summary',numeric={k for k,_ in summary_columns if k not in ('family',)}))
parts.append('</section>')
parts.append('<section><h2>左右比較図</h2><p class="note">左右で1層分の横幅を固定し、同じ座標単位を同じピクセル数で表示しています。</p>')
for filename,caption in [('random-20-2-928000.png','ランダム有向グラフ・20頂点：比較例'),('watts_strogatz-40-2-930029.png','Watts–Strogatz・40頂点：比較例')]:
    rel=f'drawings/presentation_v5/{filename}'
    parts.append(f'<figure><img loading="lazy" src="{rel}" alt="{escape(caption)}"><figcaption>{escape(caption)} — 左：線形配分、右：二乗和配分</figcaption></figure>')
parts.append('</section>')
parts.append('<section><h2>入力×方式の詳細表</h2><p class="note">1行が1つの入力と1つの配分方式です。スパンは層数、辺中心線長は完成図の座標距離です。下の検索欄で入力ID・系列・方式を絞れます。</p><input id="filter" type="search" placeholder="入力ID、系列、方式で絞り込み"><p class="note"><span class="tag">linear</span>線形配分 <span class="tag">square</span>二乗和配分</p>')
parts.append(table(detail,detail_columns,'detail'))
parts.append('</section>')
parts.append('<section><h2>入力一覧と完走状況</h2><p class="note">探索・割当・描画の状態およびソルバー目的値、下界、ギャップを方式別に掲載しています。</p>')
parts.append(table(completion,completion_columns,'completion'))
parts.append('</section><footer>生成元: summary.csv, per_graph_metrics.csv, input_completion.csv。再生成: <code>./theme2026-saku/bin/python output/torus_balance_diff_square_20261126/render_tables.py</code></footer></main><script>const f=document.getElementById("filter");f.addEventListener("input",()=>{const q=f.value.toLowerCase();document.querySelectorAll("#detail tbody tr").forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(q));});</script></html>')
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size} bytes); summary={len(summary)}, detail={len(detail)}, completion={len(completion)}")
