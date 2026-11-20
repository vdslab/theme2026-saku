"""Render the validation experiments as an offline report with linked raw results."""

from argparse import ArgumentParser
from collections import Counter
from html import escape
import json
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

from report_torus_study import (STYLE, difference_chart, figure, fmt, label, pair_table, save,
                                section, stat_line, style_axes, table)
from run_torus_validation import GROUPS
from torus_study.validation_inputs import read_jsonl

ORIENTATIONS = (
    ("coherent","円環に沿う","Coherent"),
    ("flip_quarter","各辺を確率0.25で反転","25% reversal"),
    ("random_direction","ランダムな向き","Random direction"),
    ("acyclic","ランダム順序に沿うDAG","Acyclic"),
)
DESIGN = {
    "topology":("同一骨格で向きだけ変える", "循環性と辺の向きの揃い方を切り分ける"),
    "scc_control":("全頂点を同じSCCに保った方向比較", "強連結性の有無を固定して向きの効果を確かめる"),
    "public":("循環のある実データ", "前回の非巡回中心の公開標本を補う"),
    "public_retry":("実データの未完走例の再試行", "求解制限と描画処理による打ち切りを調べる"),
    "budget":("同じ時計予算での方式比較", "比較方式の時間切れに伴う選択偏りを確認する"),
    "ranks":("層割当と実行可能初期解", "固定した巻き辺数の下で目的関数と初期解を比較する"),
    "winding":("巻き数を含む小規模厳密照合", "前回の巻き数固定の照合を拡張する"),
    "sifting":("siftingの別初期順と探索予算", "追加試行による改善と計算量を比較する"),
    "seams":("切れ目候補選択の再検証", "ガードと元辺本数優先を新規入力で検証する"),
    "seam_stress":("長辺・複数巻きの切れ目全列挙", "元辺本数と線分本数の目的が異なる入力を調べる"),
    "coordinates":("座標の周期・曲がり重み・平滑化", "辺長と曲がりの効果を同一埋め込みで分離する"),
    "coordinate_audit":("LPの交差数の照合", "描画計測器とリフト上の独立計数を比較する"),
    "scaling":("二次・線形分配の規模限界", "ライセンス制限と処理規模を分離する"),
    "subdivision":("長い辺が多い場合の挿入時間", "ダミー頂点増大時に索引化の効果が残るかを測る"),
    "geometry":("境界の移動に対する交差計数", "周期境界の位置と巻き数を変えて不変性を試す"),
}


def pair(rows, left, right, metric, where=lambda r:True):
    def observed(variant):
        return {r["case"]:r[metric] for r in rows if r["variant"]==variant and
                r["status"]=="ok" and metric in r and where(r)}
    a,b=observed(left),observed(right)
    return [(c,a[c],b[c]) for c in sorted(a.keys()&b.keys())]


def contrast(rows, descriptions):
    return pair_table("対応比較。左の条件 − 右の条件", [
        stat_line(n,pair(rows,a,b,m)) for n,a,b,m in descriptions
    ])


def method_status(rows, variants):
    result=[]
    for method in variants:
        group=[r for r in rows if r["variant"]==method]
        counts=Counter(r["status"] for r in group)
        other="、".join(f"{s} {n}" for s,n in sorted(counts.items()) if s!="ok")
        result.append((method,len(group),counts["ok"],other or "—"))
    return result


def page(root):
    data={g:read_jsonl(root/g/"rows.jsonl") for g in GROUPS}
    manifest={g:read_jsonl(root/g/"inputs.jsonl") for g in GROUPS}
    inventory=table("追試の一覧",("追試","検証すること","入力","測定行","完了行","生データ"),[
        (title,detail,len(manifest[g]),len(data[g]),sum(r["status"]=="ok" for r in data[g]),g+"/results.csv")
        for g,(title,detail) in DESIGN.items()
    ])
    inventory_links="<ul>"+"".join(
        f'<li>{escape(DESIGN[g][0])} — <a href="{g}/results.csv">CSV</a> · <a href="{g}/inputs.jsonl">入力</a> · <a href="{g}/rows.jsonl">詳細</a> · <a href="{g}/settings.json">設定</a></li>'
        for g in GROUPS)+"</ul>"
    overview=section("overview","結論と追試一覧",'''
<p><strong>辺の向きが円環に沿う条件で利点が再現した。</strong> 同じ骨格で向きだけを変えると、Graphviz dotに対する交差差は平均−3.00から＋7.05に変わった。実在の有向ネットワークは、再試行を含めて比較できた10条件すべてでトーラスの交差が多かった。</p>
<p><strong>境界処理ではDP単独の候補を残す価値がある。</strong> 追加の28件で通過線分が2件改善した。長辺と複数巻きを含む人工ストレスでは、通過線分数を最小化すると通過元辺数が最小にならない例を2件確認した。</p>
<p><strong>同じ配置情報で座標だけを変えた場合、交差数は不変だった。</strong> 独立計数と層順・巻き数による計数は144条件で一致した。汎用計測器の微差は今後の座標比較の根拠から外す。</p>
<p>下表の15グループを実行した。フルライセンスの接続確認も行った。参加者実験は提示・計時・記録・採点の準備と動作確認まで実施した。</p>
'''+inventory+f'<details><summary>生データ・入力・設定を開く</summary>{inventory_links}</details>')

    orient_items=[(english,pair(data["topology"],"torus","dot","geometric_crossings",
                 lambda r:r["orientation"]==key)) for key,_,english in ORIENTATIONS]
    orient_chart=difference_chart(root,"orientation",orient_items,"Geometric crossings: Torus minus Graphviz dot")
    orient_table=pair_table("Graphviz dotとの交差差。方向条件ごとに独立の骨格20件",[
        stat_line(jp,entry[1]) for (_,jp,_),entry in zip(ORIENTATIONS,orient_items,strict=True)])
    interaction_rows=[]
    topology=data["topology"]
    for key,jp,_ in ORIENTATIONS[1:]:
        by={(r["block"],r["orientation"],r["variant"]):r["geometric_crossings"]
            for r in topology if r["status"]=="ok"}
        comparisons=[]
        for block in sorted({r["block"] for r in topology}):
            ids=[(block,o,v) for o in (key,"coherent") for v in ("torus","dot")]
            if all(i in by for i in ids):
                a,b,c,d=(by[i] for i in ids)
                comparisons.append((block,a-b,c-d))
        interaction_rows.append(stat_line(jp+" − 円環に沿う",comparisons))
    scc_items=[
        stat_line(desc,pair(data["scc_control"],"torus","dot","geometric_crossings",
            lambda r:r["orientation"]==key))
        for key,desc in (("coherent","追加辺も円環沿い"),("random_chords","追加辺をランダムに反転"),
                         ("counter_chords","追加辺をすべて逆向き"))
    ]
    topology_block=section("topology","1. 循環方向が揃うときの効果",'''
<p>同じ無向Watts–Strogatz骨格を、12・16頂点、再配線率0.10・0.35、各5 seedで生成した。骨格ごとに4種の有向化を行い、ラベルと辺集合を固定した。トーラスとdotは80条件とも完走した。各辺を確率0.25で反転する条件とランダム条件には共通乱数を使った。</p>
'''+figure(orient_chart,"辺の向き4条件の交差数差と信頼区間。円環に沿う条件で平均が負。",
           "点は平均、線は対応のあるグラフ単位のbootstrap 95%区間。左側ではトーラスの交差が少ない。")
        +orient_table+pair_table("同じ骨格での交差差の差",interaction_rows)+'''
<p>円環沿いでは20件中14件で交差が減り、ランダム方向では18件で増えた。元の階層方向と整合するような辺の向きが特に重要だと解釈できる。</p>
<h3>全頂点を一つのSCCに固定</h3>
<p>12・16頂点の有向閉路に同じ追加辺を入れ、追加辺の向きだけを変えた。強連結性を30条件すべてで保った。</p>
'''+pair_table("SCCを固定したときの交差差。トーラス − dot",scc_items)+'''
<p>各条件10件で、平均差は円環沿い−2.50、ランダムに反転＋5.40、すべて逆向き＋5.60。今回の方向効果を「SCCがない図との違い」だけでは説明できない。フィードバック辺数・次数は向きとともに変わり得る。</p>''')

    public_results=data["public"]
    retries={r["case"]:r for r in data["public_retry"] if r["variant"]=="native"}
    extras={r["case"]:r for r in data["public_retry"] if r["variant"]=="one_round_linear"}
    by={(r["case"],r["variant"]):r for r in public_results}
    public_table=[]
    for r in manifest["public"]:
        case=r["id"]; dot=by[case,"dot"]; first=by[case,"torus"]; retry=retries.get(case,{})
        final=retry if retry.get("status")=="ok" else first
        d=dot.get("geometric_crossings"); t=final.get("geometric_crossings")
        public_table.append((case,r["nodes"],r["edges"],r["largest_scc_fraction"],
                             label(first["status"]),label(retry.get("status","—")),t,d,t-d if t is not None and d is not None else None,
                             extras.get(case,{}).get("geometric_crossings")))
    public_block=section("public","2. 公開の実在有向データと未完走の確認",'''
<p>Sampsonの3時点と、UKfaculty・macaqueの最大SCCを起点にした誘導部分グラフ各4件。後者は弱連結BFSの先頭14頂点を使い、元の向きを維持した。Sampsonの時点間や誘導部分グラフ間には重複がある。求解または描画で止まった4例を、モデルごと3秒・方式ごと25秒で再試行した。</p>
'''+table("最初の試行、再試行、交差数",("入力","頂点","辺","最大SCCの割合","既定の初回","既定の再試行",
          "トーラス交差","dot交差","交差差","線形・1回掃引の交差"),public_table)+'''
<p>既定のトーラスでは3例を追加で回収し、比較できた10例すべてで交差が増えた。平均差は＋384.50で、密な部分グラフが差を押し上げている。残る1例はモデルごと8秒・方式ごと55秒まで伸ばしても、層割当中に実行可能解がないまま終わった。現実の循環があるだけで、円環沿いの人工グラフと同じ利点が得られるとは考えにくい。<a href="public_retry_extended/rows.jsonl">8秒での再試行</a></p>
<p>出典と取得形式は、各入力のマニフェストに記録した。<a href="https://github.com/networkx/networkx/blob/main/examples/drawing/sampson_data.zip">Sampson</a> · <a href="https://github.com/igraph/igraphdata/tree/main/data">UKfacultyとmacaque</a></p>''')

    b=data["budget"]
    coverage=[]
    for v in ("torus","dot","sugiyama","radial"):
        rows=[r for r in b if r["variant"]==v]
        censored=[r for r in rows if r["previous_censored"]]
        values=[sum(r["status"]=="ok" and r["wall_seconds"]<=t for r in rows) for t in (6,14,24)]
        coverage.append((label(v),len(rows),*values,sum(r["status"]=="ok" for r in censored),len(censored)))
    budget_block=section("budget","3. 比較方式の時計予算と選択偏り",'''
<p>前回から族ごとに時間切れを最大2例、その他を1例選んで12入力を再試行した。独立の再試行で計測した方式単位の壁時計時間を用い、仮に6・14・24秒で打ち切る場合の完了数を数えた。6秒と14秒で個別にアルゴリズムを中断して再スタートした結果ではない。</p>
'''+table("一定時間内の完了数",("方式","試行","6秒","14秒","24秒","以前に時間切れがあった入力で完了","同対象数"),coverage)+'''
<p>平面杉山法は今回14秒で12/12件、放射型は24秒でも6/12件だった。前回の平面法の一部の欠測が実行制限・負荷に敏感だったことが分かる。放射型の品質比較には依然として欠測偏りがある。新旧の実行時間は単純に同一条件とみなせない。</p>''')

    r=data["ranks"]
    rank_status=[]
    for v in ("cold_0.03","warm_0.03","cold_0.25","warm_0.25"):
        rs=[x for x in r if x["variant"]==v]
        rank_status.append((v,len(rs),sum(x["status"]=="ok" for x in rs),sum(x.get("optimal",0) for x in rs)))
    rank_block=section("ranks","4. 層割当の初期解と目的関数",'''
<p>16入力について、層数と左右通過元辺数を固定し、実行可能な割当を二次目的のMIP startとして渡す条件を比較した。WorkLimitは壁時計秒と異なるGurobiの作業量。初期解の準備費用は別行に記録した。線形総和・二乗和・最大2層増の条件では、後段も測定した。</p>
'''+table("打ち切り前の実行可能解と最適性",("条件","試行","実行可能解あり","最適終了"),rank_status)
        +contrast(r,[("二乗和 − 線形／スパン二乗和","square_diff","linear_diff","span_square_sum"),
                     ("二乗和 − 線形／完成図交差","square_diff_drawing","linear_diff_drawing","geometric_crossings"),
                     ("最大2層追加 − 既定／完成図交差","square_two_extra_layers_drawing","square_diff_drawing","geometric_crossings")])+'''
<p>低予算では初期解なしの14/16件に対し、ありは16/16件で解を返した。最適終了は双方13件。より高い予算では最適終了が15件から16件になった。同じ層数で二乗和は狙った指標を改善したが、完成図の交差は平均＋0.88だった。層数を増やす場合も完成図への効果には両方向があった。</p>''')

    w=data["winding"]; s=data["sifting"]
    bounded=sum(r.get("within_bound_by_common_shift",False) for r in w if r["variant"]=="current_free")
    winding_block=section("winding","5. 巻き数の厳密照合と探索のやり直し",f'''
<p>3層・各層2または3頂点の20例で、全順序と巻き数の組合せを列挙した。各層間に共通の整数を加減しても交差が変わらない性質を使い、自由siftingの解が各層間で−1〜＋1に収まるかも確認した。該当は{bounded}/20件。別の16件では前段を固定し、siftingの反復、巻き数固定と自由、初期順を変えた複数開始を比較した。</p>
'''+contrast(w,[("任意巻き±1の最適値 − 巻き数0の最適値","oracle_1","oracle_0","crossings"),
                ("自由sifting − 任意巻き±1の厳密値","current_free","oracle_1","crossings")])
    +contrast(s,[("1回 − 既定／交差","one_round","current","crossings"),
                 ("固定と自由の良い方 − 既定／交差","fixed_or_free","current","crossings"),
                 ("4開始の最良 − 既定／交差","best_of_four","current","crossings"),
                 ("4開始の総時間 − 既定 (s)","best_of_four","current","search_seconds")])+'''
<p>巻き数の自由化で小規模の厳密値が20例中9例で改善した。自由siftingは20例すべてで制限付きの厳密値と一致したが、19例で厳密値が0の小さな問題である。別の16例では1回の交差が既定と同数だったのは15例。4開始は5例で改善したが計算時間も増えた。複数開始を常時使う効果は小さい。</p>''')

    a=data["seams"]; stress=data["seam_stress"]
    fits=[r for r in stress if r["variant"]=="cut_oracle" and r["status"]=="ok"]
    dp={r["case"]:r["seam_segments"] for r in stress if r["variant"]=="dp" and r["status"]=="ok"}
    distinct=[r for r in fits if r["edges_at_segment_minimum"]>r["original_edge_minimum"]]
    boundary_block=section("seams","6. 境界を通る線分と元の辺",f'''
<p>前回に見つけた「UNWINDなしのDPを追加候補に残す」方法を新規28例で検証。候補間の同点処理では線分数、元辺数、通過イベント数を順に比較した。人工ストレスでは固定した層構造に長辺を多く入れ、巻き数を−2〜＋2にして切れ目を全列挙した。</p>
'''+contrast(a,[("候補追加 − 既定／上下通過線分","guarded","current","seam_segments"),
                ("候補追加 − 既定／上下通過元辺","guarded","current","seam_edges"),
                ("候補追加 − 既定／完成図交差","guarded","current","geometric_crossings"),
                ("元辺優先 − 線分優先／上下通過元辺","edges_then_segments","segments_then_edges","seam_edges")])
    +table("二つの目的が異なる人工例",("ケース","最少線分数","そのときの最少元辺数","最少元辺数","そのときの最少線分数"),[
        (r["case"],r["segment_minimum"],r["edges_at_segment_minimum"],r["original_edge_minimum"],
         r["segments_at_original_edge_minimum"]) for r in distinct])
    +f'<p>候補追加は2/28件で通過線分を減らし、幾何交差は全件同数だった。候補内の優先順位変更では差が出なかった。人工例では36件中{len(distinct)}件で目的が食い違った。DPと線分最少値は{sum(dp.get(r["case"])==r["segment_minimum"] for r in fits)}/{len(fits)}件で一致した。元辺の通過本数を最小化したい場合は別の目的関数が必要である。</p>')

    c=data["coordinates"]
    config=("bk_k0_p1","bk_k4_p1","bk_k10_p1","lp_w0_p1","lp_w025_p1","lp_w1_p1","lp_w4_p1",
            "lp_w1_p1.25","lp_w1_p1.6","replica_3x3","matched_period_bk")
    coord_table=[]
    for method in config:
        good=[r for r in c if r["variant"]==method and r["status"]=="ok"]
        coord_table.append((method,len(good),*(mean(r[k] for r in good) for k in
                            ("period_factor","bends","total_edge_length","seconds"))))
    c_pairs=[("LP weight .25","lp_w025_p1"),("LP weight 1","lp_w1_p1"),("LP weight 4","lp_w4_p1")]
    coord_chart=difference_chart(root,"bend_weight",[(name,pair(c,v,"lp_w0_p1","bends"))
                                             for name,v in c_pairs],"Change in bends vs. LP without penalty")
    audit=[r for r in data["coordinate_audit"] if "strip_crossings" in r]
    mismatch=[r for r in audit if r["strip_crossings"]!=r["geometric_crossings"]]
    coord_block=section("coordinates","7. 座標割当と交差カウントの再監査",'''
<p>16入力に対し、同じ階層・層順・巻き数から座標だけを変えた。周期を最小設定の1・1.25・1.6倍とし、BKの平滑化とLPの曲がり罰則の重みを振った。3×3 BKは、その周期に合わせた既定BKとも比較した。</p>
'''+figure(coord_chart,"曲がり罰則の重みを増やすと、重みゼロに比べ平均の曲がり数が減る図。",
           "周期を揃えた重みの比較。統計単位は入力グラフ。")
    +table("各方式の代表条件の平均",("方式","対応入力","周期倍率","曲がり","総辺長","割当秒"),coord_table)
    +contrast(c,[("重み1 − BK／曲がり","lp_w1_p1","bk_k4_p1","bends"),
                 ("重み4 − 重み1／総辺長","lp_w4_p1","lp_w1_p1","total_edge_length"),
                 ("周期1.6倍 − 最小周期／総辺長","lp_w1_p1.6","lp_w1_p1","total_edge_length"),
                 ("3×3 − 同周期BK／曲がり","replica_3x3","matched_period_bk","bends"),
                 ("3×3 − 同周期BK／総辺長","replica_3x3","matched_period_bk","total_edge_length")])
    +f'''
<p>最小周期で重み1のLPは既定BKの曲がりを16件すべてで減らした。総辺長は16件中8件で短縮、8件で増加。重み4で曲がりがさらに減る一方、重み1より総辺長が平均1.21増えた。3×3は同周期で曲がりを平均8.69減らしたが、総辺長は全件増えた。</p>
<h3>交差数の監査</h3>
<p>同じ埋め込みの{len(audit)}条件で、層間帯をリフトして交点を独立に数えた。層順・巻き数の計数とは{sum(r["strip_crossings"]==r["embedding_crossings"] for r in audit)}/{len(audit)}件で一致した。全方式共通の線分クリッピング計測器だけが{len(mismatch)}件でずれた。ずれはLP系に限られた。座標方式間で交差が微増減したように見える値は効果と解釈しない。上の評価は辺長・曲がりに基づく。</p>
'''+table("独立計数と汎用計測器が異なった条件",("入力","方式","独立計数","汎用計測器"),[
        (r["case"],r["variant"],r["strip_crossings"],r["geometric_crossings"]) for r in mismatch]))

    scale=data["scaling"]
    wls=read_jsonl(root/"wls_probe"/"rows.jsonl")[0]
    series=[r for r in scale if r["variant"]=="diff_drawing_one_round" and r["status"]=="ok"]
    fig,ax=plt.subplots(figsize=(7.6,3.6),layout="constrained")
    for family,color in (("dag","#176a9b"),("watts_strogatz","#087d73")):
        scores=sorted((r["nodes"],r["crossing_seconds"]) for r in series if r["family"]==family)
        ax.plot(*(list(zip(*scores))),marker="o",color=color,label="DAG" if family=="dag" else "Watts–Strogatz")
    ax.set(xlabel="Original vertices",ylabel="Crossing stage (seconds; one round)")
    ax.legend(frameon=False)
    style_axes(ax)
    scale_chart=save(fig,root,"scaling_linear")
    model_rows=[]
    for r in manifest["scaling"]:
        selected={x["variant"]:x for x in scale if x["case"]==r["id"]}
        two=selected.get("diff_square_rank",{}); linear=selected.get("diff_rank",{})
        end=selected.get("diff_drawing_one_round",{})
        model_rows.append((label(r["family"]),r["nodes"],r["nodes"]+r["edges"],
                           label(two.get("status","—")),two.get("solver_errno"),
                           label(linear.get("status","—")),end.get("crossing_seconds"),
                           "あり" if end.get("solver_limited") else "なし"))
    scaling_block=section("scaling","8. 規模とライセンスの影響",'''
<p>36・60・90・120頂点で、DAGとWatts–Strogatzの両方を試した。左右通過元辺数の探索は共通にし、層割当の二乗和と線形総和を切り替えた。後段の交差削減は1回の条件で完了できるかを別計測した。計測の家族・規模ごとの反復は1。</p>
'''+figure(scale_chart,"線形分配で完了した8入力の、1回掃引の交差削減時間。",
           "線形総和による分配の後段。各点は1入力で、漸近的な計算量の推定には使用しない。")
    +table("実際の層割当と後段",("族","頂点","階層変数","二次求解","エラー番号","線形求解","交差削減秒","上流の制限付き解"),model_rows)
    +f'''
<p>二次は90・120頂点の4入力すべてで制限エラー10010。線形は8/8件で層割当から1回掃引と座標生成まで完了し、120頂点も通った。時間制限付きの上流結果を含む。WLSで201変数の二次問題を再試行した結果は <code>{escape(wls["status"])}</code>（{fmt(wls.get("solver_errno"))}）。ネットワークアクセスを許可した確認でも同じ状態だった。そのためフルライセンスでの既定法の限界や120頂点での通常の5回掃引はここでは確定していない。<a href="wls_escalated/rows.jsonl">再確認の記録</a></p>
''')

    sub=data["subdivision"]
    geom=data["geometry"]
    sub_rows=[]
    for r in manifest["subdivision"]:
        rows={x["variant"]:x for x in sub if x["case"]==r["id"]}
        old, new=rows["legacy"],rows["indexed"]
        sub_rows.append((r["nodes"],r["height"],old["dummy_nodes"],old["segments"],
                         old["seconds"]*1000,new["seconds"]*1000,old["seconds"]/new["seconds"]))
    geom_rows=[]
    expected={r["case"]:r["geometric_crossings"] for r in geom if r["variant"]=="original"}
    for variant in ("original","layer_cut_rotation","global_seam_translation"):
        sample=[r for r in geom if r["variant"]==variant]
        geom_rows.append((variant,len(sample),sum(r["geometric_crossings"]==expected[r["case"]] for r in sample),
              sum(r["geometric_crossings"]==r["crossings"] for r in sample)))
    validation_block=section("validation","9. ダミー挿入と周期境界の性質",'''
<p>長辺を多くして、50・200・800頂点で旧版と索引化版を各9回ずつ、順番を交互にして計測した。別に人工の周期グラフ36例で−2〜＋2巻きの線分を作り、層ごとの切れ目の回転と全層一括移動を施した。</p>
'''+table("長スパン入力の挿入時間",("頂点","層","ダミー数","線分数","旧 (ms)","索引あり (ms)","旧／索引"),sub_rows)
    +table("周期の表現を変える前後の交差",("条件","入力","元の幾何交差と一致","層順の計数と一致"),geom_rows)+'''
<p>ダミー挿入は全反復で出力が完全に一致し、800頂点では中央値が約1.58倍高速だった。幾何交差は人工36例の両変換で保存した。座標が数値的な境界近傍にある場合は、第7節の独立計数を優先する。</p>''')

    human=section("readability","10. 読み取りの参加者実験",'''
<p>前回作成した24問×3条件を、実際に提示・計時できるオフライン画面にした。匿名IDと担当者の割り当てたフォーム番号を入力し、画像表示後の回答と画面切替の有無をCSVに記録する。採点器は中断した参加者を除く設定を追加し、既知の確認用回答で検証した。</p>
<p class="caution">参加者の回答CSVは入手できていない。したがって、人が境界をまたぐ辺や経路をどれだけ早く正確に読めるかの実測値はない。</p>
<p><a href="readability/index.html">実験提示画面</a> · <a href="readability/build.json">刺激の検証記録</a> · <a href="../../documents/experiment_validation.md">実施・採点手順</a></p>''')

    blocks=(overview,topology_block,public_block,budget_block,rank_block,winding_block,boundary_block,
            coord_block,scaling_block,validation_block,human)
    names=(("overview","追試一覧"),("topology","辺方向"),("public","実データ"),("budget","時計予算"),
           ("ranks","層割当"),("winding","巻き数・探索"),("seams","境界"),("coordinates","座標"),
           ("scaling","規模"),("validation","検査"),("readability","読み取り"))
    nav="".join(f'<li><a href="#{anchor}">{name}</a></li>' for anchor,name in names)
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>トーラス階層グラフ描画の追試結果</title><style>{STYLE}</style></head>
<body><a class="skip" href="#main">本文へ移動</a>
<header><div class="date">2026.11.20</div><h1>トーラス階層グラフ描画の追試結果</h1>
<p>前回の所見を検証する15の計算グループと、参加者実験に向けた提示・計時・採点の準備。</p></header>
<nav aria-label="目次"><ul>{nav}</ul></nav><main id="main">{"".join(blocks)}</main>
<footer><p><a href="../torus_experiment_20261120/index.html">前回報告書</a> · <a href="../../documents/experiment_validation.md">追試の手順</a> · <a href="wls_probe/rows.jsonl">ライセンス確認記録</a></p></footer>
</body></html>"""


def main():
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("results",type=Path)
    args=parser.parse_args()
    (args.results/"index.html").write_text(page(args.results),encoding="utf-8")


if __name__=="__main__":
    main()
