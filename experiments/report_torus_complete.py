"""Assemble the consolidated offline report from archived experiment reports and data."""

from argparse import ArgumentParser
from collections import Counter
from html import escape
from itertools import groupby
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from report_torus_study import (
    STYLE, BLUE, ORANGE, TEAL, figure, pair_table, paired, read_csv, read_rows,
    save, section, stat_line, style_axes, table,
)
from matplotlib import pyplot as plt

INITIAL = "torus_experiment_20261120"
VALIDATION = "torus_validation_20261120"
TITLE = "トーラス階層グラフ描画の総合実験報告書"
EXTRA_STYLE = """
body{background:#f3f7f9}
header{padding-block:clamp(2.4rem,7vw,5.7rem)}
header h1{max-width:67rem;letter-spacing:-.03em}
header .actions{display:flex;gap:.65rem;flex-wrap:wrap;margin-top:1.45rem}
.actions a{color:#fff;text-decoration:none;border:1px solid #6595a8;padding:.4rem .8rem;border-radius:.45rem}
.actions a:first-child{background:#d8f4ee;color:#0d382e;border-color:#d8f4ee}
nav a{text-decoration:none}
nav a:hover,.actions a:hover{text-decoration:underline}
section>p,section>ul{max-width:71ch}
.card strong{font-size:1.1rem;margin:.08rem 0 .35rem}
.card p{margin:.12rem 0 .2rem}
.table-wrap.prose td{text-align:start;min-width:11rem}
.table-wrap.prose th[scope=row]{min-width:8rem}
.table-wrap.index th[scope=row]{overflow-wrap:normal}
.table-wrap.index td:last-child{text-align:start;min-width:13rem}
.detail{border-block-start:1px solid var(--line);padding-top:.75rem;margin-top:1.25rem}
.detail[open]>summary{margin-bottom:.62rem}
.detail h3{font-size:1.12rem}
.key-source{color:var(--muted);font-size:.9rem}
pre{padding:.8rem 1rem;overflow:auto;background:#f2f6f9;border:1px solid var(--line)}
.sources li{margin-block:.45rem}
@media(max-width:40rem){nav a{font-size:.88rem}table{min-width:32rem}.table-wrap.prose table{min-width:39rem}}
@media print{.actions{display:none!important}.table-wrap{overflow:visible}.detail{break-inside:auto}}
"""


class ArchivedReport:
    def __init__(self, folder):
        self.folder = folder
        markup = (folder / "index.html").read_text(encoding="utf-8")
        self.sections = {
            anchor: (title, content)
            for anchor, title, content in re.findall(
                r'<section id="([^"]+)"><h2>(.*?)</h2>(.*?)</section>', markup, re.S
            )
        }

    def body(self, anchor):
        _, raw = self.sections[anchor]

        def relocate(match):
            attribute, target = match.groups()
            if not urlsplit(target).scheme and not target.startswith(("#", "/")):
                target = f"../{self.folder.name}/{target}"
            return f'{attribute}="{target}"'

        return re.sub(r'\b(href|src)="([^"]+)"', relocate, raw)

    def details(self, anchor, label=None):
        original, _ = self.sections[anchor]
        return details(label or original, self.body(anchor))


def details(label, content):
    return f'<details class="detail"><summary>{escape(label)}</summary>{content}</details>'


def prose_table(caption, headers, rows):
    return table(caption, headers, rows).replace('class="table-wrap"', 'class="table-wrap prose"', 1)


def link(path, label):
    return f'<a href="{escape(str(path))}">{escape(label)}</a>'


def citations():
    reference = (
        ("杉山・田川・戸田（1981）", "階層化した有向グラフの描画を工程に分け、ランダムな階層で交差削減を厳密値と比較した。工程単体と完成図を併せて測る構成の出発点。", "https://doi.org/10.1109/TSMC.1981.4308636"),
        ("Gansner ほか（1993）", "階層化、層内順序、座標、配線という実用パイプラインを提示。Graphviz dotを外部対照に置く根拠。", "https://doi.org/10.1109/32.221135"),
        ("Healy・Nikolov（2002）", "寸法制約を伴うDAGの階層化を評価。層数に加え、総スパン・層幅・ダミー数を測る設計につなげた。", "https://pure.ul.ie/en/publications/how-to-layer-a-directed-acyclic-graph/"),
        ("Bachmaier ほか（2008）", "循環階層のスパンを、小規模の厳密値と大規模の時間計測で評価。多点開始の品質と時間の両方を調べた。", "https://www.infosun.fim.uni-passau.de/~chris/down/CyclicLeveling.pdf"),
        ("Eiglsperger ほか（2005）", "長辺の多い人工例とランダム入力で、正規化後の規模・時間・交差を測定。今回のダミー挿入比較と規模指標に対応。", "https://www.kurims.kyoto-u.ac.jp/EMIS/journals/JGAA/accepted/2005/EiglspergerSiebenhallerKaufmann2005.9.3.pdf"),
        ("Jünger・Mutzel（1997）", "2層の片側固定と両側可変を分け、厳密法との比較と密度・規模を振った評価を実施。小規模全列挙と探索回数の比較に対応。", "https://doi.org/10.7155/jgaa.00001"),
        ("Bachmaier（2007）", "放射・平面と交差削減法の組合せを比較し、交差改善と計算費用を評価。円形重心・回転・共通巻き除去の分離に対応。", "https://www.infosun.fim.uni-passau.de/~chris/down/RadialVisualization.pdf"),
        ("Bachmaier ほか（2011）", "正規化後のサイズ・掃引回数・ダミー間交差を測定し、品質改善に伴う時間を報告。今回も交差・反復・時間を同時に測った。", "https://doi.org/10.7155/jgaa.00242"),
        ("Brandes・Köpf（2002）", "固定した順序上で各方向の整列・圧縮を統合し、辺の直線性と幅を評価。今回のBK内部処理の比較に対応。", "https://d-nb.info/1104942232/34"),
        ("Jünger・Mutzel・Spisla（2019）", "共通の前段で座標方式を比較し、幅、辺長、時間のトレードオフを評価。周期を固定した座標比較に対応。", "https://jgaa.info/index.php/jgaa/article/download/paper500/2456/2263"),
        ("Di Battista ほか（2000）", "公開入力と生成DAGで複数の描画方式を比較し、交差・曲がり・面積で優劣が変わることを示した。今回の全体評価を多指標にした。", "https://doi.org/10.1142/S0218195900000358"),
        ("Bachmaier ほか（2012）", "最後の層から最初の層に戻る循環階層を描画し、閉路を一方向に追える例を示した。今回の円筒対照と逆行辺計数に対応。", "https://www.kurims.kyoto-u.ac.jp/EMIS/journals/JGAA/accepted/2012/BachmaierBrandenburgBrunnerFulop2012.16.2.pdf"),
        ("Lionakis ほか（2022）", "階層図を計算指標と参加者の到達可能性・最短路課題で評価。", "https://arxiv.org/html/2209.04522"),
        ("Chen ほか（2020）", "トーラスの周辺文脈とパン操作によるリンク・経路読解を評価。", "https://ialab.it.monash.edu/~dwyer/papers/DoughNets.pdf"),
    )
    items = "".join(f'<li><strong>{author}</strong>。{explanation} {link(url, "一次資料")}</li>'
                    for author, explanation, url in reference)
    return f'<ul class="sources">{items}</ul>'


def primary_comparisons(initial, validation, output):
    observations = read_rows(initial.folder, "framework_timed")
    definitions = (
        ("平面杉山との幾何交差", "sugiyama", "geometric_crossings"),
        ("dotとの幾何交差", "dot", "geometric_crossings"),
        ("同じ層割当を使った円筒との幾何交差", "cylindrical_reference", "geometric_crossings"),
        ("平面杉山との逆行辺", "sugiyama", "reverse_direction_edges"),
        ("平面杉山との境界通過元辺", "sugiyama", "either_seam_edges"),
    )
    summary = [
        stat_line(title, paired(observations, "framework", "torus", control, metric))
        for title, control, metric in definitions
    ]
    raw = read_rows(validation.folder, "public")
    recovered = read_rows(validation.folder, "public_retry")
    dot = {row["case"]: row["geometric_crossings"] for row in raw
           if row["variant"] == "dot" and row["status"] == "ok"}
    torus = {row["case"]: row["geometric_crossings"] for row in raw + recovered
             if row["variant"] in ("torus", "native") and row["status"] == "ok"}
    public_pairs = [(case, torus[case], dot[case]) for case in sorted(torus.keys() & dot.keys())]
    differences = [
        (case, torus.get(case), dot[case], torus[case] - dot[case] if case in torus else None)
        for case in sorted(dot)
    ]
    chart = public_crossing_chart(output, public_pairs)
    return (
        pair_table("初回・統制生成グラフの主な対応比較", summary)
        + figure(chart, "公開有向データで比較できた10条件の交差差。すべてトーラスの交差が多い側。",
                 "点は比較できた公開入力1条件。0より右はトーラスの交差が多い。個々の差と未完走の1条件は下表。")
        + table("公開有向データの交差数。初回と再試行で得られた既定トーラス",
                ("入力", "トーラス", "dot", "トーラス − dot"), differences)
    )


def public_crossing_chart(output, pairs):
    fig, ax = plt.subplots(figsize=(8.4, 3.3), layout="constrained")
    style_axes(ax)
    series = (("sampson", "Sampson", TEAL), ("UKfaculty", "UKfaculty", BLUE),
              ("macaque", "Macaque", ORANGE))
    labels = []
    for index, (prefix, name, color) in enumerate(series):
        differences = sorted(a - b for case, a, b in pairs if case.startswith(prefix))
        positions = [index + .09 * (i - (len(differences) - 1) / 2)
                     for i in range(len(differences))]
        ax.scatter(differences, positions, s=48, color=color, edgecolor="white", linewidth=.8, zorder=3)
        labels.append(f"{name} (n={len(differences)})")
    ax.axvline(0, color="#596b78", linewidth=1)
    ax.set_yticks(range(len(series)), labels)
    ax.set_ylim(len(series) - .5, -.5)
    ax.set_xlabel("Geometric crossings: Torus minus Graphviz dot")
    ax.grid(axis="x", color="#e1e9ef", linewidth=.8)
    return save(fig, output, "public_crossings")


def audit_tables(output):
    rows = read_csv(output / "audits/drawing_domain.csv")
    audit = json.loads((output / "audits/two_layer_crossing.json").read_text(encoding="utf-8"))
    rendered = []
    key = lambda row: (row["method"], float(row["period_factor"]))
    for (method, factor), group in groupby(sorted(rows, key=key), key=key):
        counts = Counter(row["status"] for row in group)
        rendered.append((method, factor, counts["ok"], counts["outside_vertical_domain"], sum(counts.values())))
    geometry = table("2層・4頂点・2辺の交差再現例", ("計数箇所", "交差数"), [
        ("siftingの局所目的", audit["local_crossings"]),
        ("層順と巻き数の全体計数", audit["embedding_crossings"]),
        ("描画された中心線", audit["geometric_crossings"]),
    ])
    bounds = table("描画入口での座標範囲の検査", ("座標方式", "周期倍率", "範囲内", "範囲エラー", "試行"), rendered)
    invalid = sum(fail for method, factor, _, fail, _ in rendered if method == "torus_lp" and factor > 1.)
    return geometry, bounds, invalid


def inventory(initial, validation):
    file_types = (
        ("設定", "settings.json"), ("入力", "inputs.jsonl"),
        ("生データ", "rows.jsonl"), ("CSV", "results.csv"), ("対応差", "paired.csv"),
        ("状態", "cases.csv"),
    )
    content = []
    for root, label in ((initial.folder, "初回"), (validation.folder, "追試")):
        for settings in sorted(root.glob("*/settings.json")):
            folder = settings.parent
            if not (folder / "rows.jsonl").exists():
                continue
            data = json.loads(settings.read_text(encoding="utf-8"))
            budget = data.get("wall_seconds", data.get("case_seconds"))
            files = " · ".join(
                link(Path("..") / root.name / folder.name / name, title)
                for title, name in file_types if (folder / name).is_file()
            )
            counts = Counter(row.get("status", "未記録") for row in read_rows(root, folder.name))
            statuses = " · ".join(f"{state} {count}" for state, count in sorted(counts.items()))
            cells = (label, folder.name, data.get("solver_seconds"), budget, statuses)
            content.append("<tr>" + "".join(
                f'<td>{escape(str(cell)) if cell is not None else "—"}</td>' if index != 1
                else f'<th scope="row"><code>{escape(cell)}</code></th>'
                for index, cell in enumerate(cells)
            ) + f"<td>{files}</td></tr>")
    caption = "記録単位の状態とファイル。行数は同一入力の各方式・工程を含む"
    headings = ("段階","グループ","求解秒","worker秒","状態の内訳","ファイル")
    columns = "".join(f'<th scope="col">{header}</th>' for header in headings)
    return (f'<div class="table-wrap index" role="region" tabindex="0" aria-label="{caption}">'
            f'<table><caption>{caption}</caption><thead><tr>{columns}</tr></thead>'
            f'<tbody>{"".join(content)}</tbody></table></div>')


def implementation_review():
    items = (
        ("層割当の終了処理", "解なしのTIME_LIMITで解を読み、AttributeError。SolCountと終了状態を取得し、呼び出し側まで伝える。", "layering/lib/results.py"),
        ("二分探索の判定", "上界33本を得た後、7層では下界43本・実行可能解ゼロ。実行可能解と下界で目標可否を判定し、未確定を残す。", "layering/search.py"),
        ("固定条件の初期解", "厳しいWorkLimitで14/16→16/16件。探索済みの実行可能割当を層調整のMIP startに再利用する。", "layering/router.py"),
        ("二乗和モデルとライセンス", "90・120頂点の各2入力で10010。線形設定と制約・変数の診断を案内。WLSの接続結果を算法の規模限界から切り分ける。", "layering/balance/diff_square.py"),
        ("層割当の目的関数", "通過辺・層数・スパン二乗和・完成図交差が同時には改善しない。局所目的と下流の評価値を併記する。", "layering/balance/diff.py"),
        ("分割後の規模", "800頂点でダミー140,426個と線分142,826本。現行の索引化を保持し、後段の予算と計時に分割後規模を反映する。", "subdivision.py"),
        ("2層時の局所交差", "別々の帯を通る2辺を局所的に1交差と誤計上。帯ごとに交差を数え、動かした頂点の影響を合算する。", "crossing/lib/embedding.py"),
        ("全体交差の再計数", "完走68件中54件で交差削減が最長。層間・頂点別に索引を持ち、変更した帯だけ差分更新する。", "crossing/lib/crossings.py"),
        ("siftingの探索予算", "1回と5回が15/16件で同値。複数開始は5/16件で改善するが追加時間を要する。高速設定と収束停止に検証余地がある。", "crossing/sifting.py"),
        ("巻き数と回転の評価", "固定巻き数では厳密値を8/40件で逃す。回転は角度変位を21/72件で増やす。角度変位と巻き数も採否に使う場合は目的を明示する。", "crossing/lib/embedding.py"),
        ("UNWIND後の切れ目候補", "DP単独より既定処理が21/72件で悪化。現行候補とUNWINDなしDPの両結果を残して比較する。", "crossing/api.py"),
        ("線分数・元辺数・通過回数", "線分最少と元辺最少が36件中2件で食い違う。元辺と線分列の対応を持ち、目的と表示の単位を明示する。", "crossing/seam.py"),
        ("巻き数の表示", "分布表示は−1・0・＋1のみ。複数巻きも実測されているため、全巻き数と各単位の集計を出す。", "reporting.py"),
        ("BKの平滑化と射影", "4回で辺長が短くなる一方で曲がりが増える。射影の制約を保持し、平滑化の目標と強度を調整する。", "coordinates/periodic.py"),
        ("LP・QPの制約と目的", "LPは曲がり重み次第で総辺長が増加し、QPは12/72件で求解エラー。既定値の変更には品質と完走率の両方が必要。", "coordinates/optimization.py"),
        ("拡張周期の描画範囲", "LPと描画の上下端の定義が異なる。基本領域を一つのデータ契約にし、違反した条件を品質集計から外す。", "drawing/preparation.py"),
        ("3×3 BKの周期整合性", "コピー座標が独立で、前回72件中12件で中央から出る辺も配置計算から欠落。中央辺の保持と周期平行移動の整合性を確認する。", "coordinates/replicated.py"),
        ("汎用交差計数の数値差", "固定埋め込み144条件の独立計数は一致。線分の切断と丸めを使う幾何計数の9条件だけに微差が出る。", None),
        ("計時の境界", "CLIでは交差削減にダミー挿入が入り、ソルバー内時間と壁時計が混在する。壁時計を基準に工程と求解時間を別記する。", "pipeline.py"),
        ("比較実装の放射型", "24秒で6/12件のみ完了。回転・挿入候補ごとに全交差を計数する箇所が高速化候補。", None),
        ("検証入力と方式選択", "既定の生成器は辺を円環沿いに向ける。DAG、SCC固定の方向対照、元の向きの実データを残して方式選択を検証する。", None),
        ("周辺タイルの既定表示", "小標本で画像の容量が増加。", "drawing/output.py"),
    )
    rows = []
    for title, explanation, path in items:
        target = Path("../../src/torus_layout") / path if path else None
        extras = {
            "汎用交差計数の数値差": "../../experiments/torus_study/geometry.py",
            "比較実装の放射型": "../../src/radial_layout/crossing_reduction.py",
            "検証入力と方式選択": "../../src/generator/watts_strogatz.py",
        }
        rows.append((title, explanation, target or extras[title]))
    result = prose_table("確認事項と実装の見直し", ("箇所", "根拠と修正方針", "該当コード"), [
        (title, explanation, str(target)) for title, explanation, target in rows
    ])
    for target in set(target for _, _, target in rows):
        label = Path(target).name
        result = result.replace(f"<td>{escape(str(target))}</td>", f"<td>{link(target, label)}</td>")
    return result


def build(output):
    initial = ArchivedReport(output.parent / INITIAL)
    validation = ArchivedReport(output.parent / VALIDATION)
    geom, bounds, invalid = audit_tables(output)
    followup = validation.body("coordinates")
    followup = followup.replace(
        "<h3>交差数の監査</h3>",
        '<p class="caution">この表は当時の計算出力を収録している。拡張周期のLPには描画入口で範囲エラーとなる行が含まれるため、拡張周期の集計は候補の比較に使わない。最小周期のLPと同周期BKの比較は以下の本文の結論を参照。</p><h3>交差数の監査</h3>',
    )
    summary = section("summary", "要旨", """
<p>トーラス上に有向階層を描く方式について、完成図、個別工程、求解と描画の正しさを評価した。初回の統制生成・公開データ比較、15グループの追試、実装上の不一致を確認した再現試験を、工程ごとに照合した。</p>
<div class="summary">
<div class="card"><strong>向きが揃うと交差が減る</strong><p>同じ骨格20件で円環に沿う方向はdotより平均3.00交差少なく、ランダム方向は7.05多かった。SCCを一つに保った対照でも再現した。</p></div>
<div class="card"><strong>実在有向データでは交差が増えた</strong><p>再試行を含め比較できた10条件すべてでdotより多かった。残る1条件は層探索中に停止した。</p></div>
<div class="card"><strong>境界の選び方は改善できる</strong><p>DPは固定埋め込みの線分最少値と一致。UNWINDなしの候補も残すと交差を変えずに通過線分を減らせる例があった。</p></div>
</div>
<p>トーラスは辺の向きを階層の進行に保つうえで有用だった。交差、境界を通る辺、曲がり、計算時間には別々の制約がある。フルライセンス環境での規模限界は未測定。</p>
""")
    method = section("methods", "方法と既往研究", """
<p>比較対象は現行トーラス、平面杉山、放射型、Graphviz <code>dot</code>。内部対照の円筒条件ではトーラスの層割当を使い、層内方向の巻き数を0に固定した。パイプラインは層割当、ダミー挿入、層内順の初期化、sifting、回転・共通巻きの除去・切れ目選択、座標割当、周期境界での描画で構成する。</p>
<p>初回の主比較は4生成族、10・16頂点、辺数2n・4n、各3 seedの48入力。工程別は24頂点を含む72入力を基本とした。公開GraphMLの小標本は29件。追試では同じ無向骨格を有向化する条件、SCC固定、元から有向のネットワーク、予算・単体処理・規模の比較を加えた。計画に記載した大きい生成サイズと反復数は、実行時の予算とライセンスに合わせて絞った。</p>
<p>交差は中心線の横切りを異なる元辺ごとに数え、重なりと接触を分けた。逆行辺は階層進行に対する逆行で、元の矢印そのものは平面・放射でも復元する。上下については通過した元辺、分割線分、巻きの回数を区別した。条件差は同じ入力に対する対応差。区間は入力単位のbootstrap 2,000反復による探索的な95%区間で、完走し両指標が揃った組で計算した。入力が重複する公開標本では個別の差を重視した。</p>
""" + details("文献ごとの実験意図と今回の設計への反映", citations())
        + '<p class="key-source">資料 ' + link("../../documents/experiment_plan.md", "元の実験計画")
        + " · " + link("../../documents/sugiyama_experiment_literature_review.md", "文献調査の全文") + "</p>")
    framework = section("framework", "1. フレームワーク全体", """
<p>初回の統制生成では、平面杉山との41組で逆行辺が平均5.32本減り、幾何交差が13.54増えた。dotとの48組では交差が平均25.48増加。同じ層割当の円筒との48組では46組で交差が減り、平均差は−22.00だった。第二の周期方向に交差を減らす効果がある一方、境界をまたぐ元辺は円筒より平均7.44本多かった。</p>
<p>初回のWatts–Strogatzの好結果を受け、追試で骨格を固定し、辺の向きだけを4通りに変えた。最も改善したのは円環に沿う向きで14/20件がdotより少ない。部分反転、ランダム、DAGでは平均差が正になった。SCC固定でも円環沿いは平均−2.50、追加辺のランダム反転は＋5.40、追加辺を逆向きにすると＋5.60だった。循環の有無だけで適用範囲を決めるには根拠が足りない。</p>
<p>初回の公開GraphML 29件は、Romeの有向化後も含め全件DAGだった。そこでSampsonの3時点、UKfacultyとmacaqueの14頂点の誘導部分グラフを各4件計測した。トーラスは初回7/11件、再試行後10/11件。比較できた10件すべてでdotより交差が多く、平均差＋384.50、中央値＋249。時点と誘導部分グラフの重複があるため、これは採用した実例の記述結果である。</p>
""" + primary_comparisons(initial, validation, output)
    + initial.details("framework", "初回の全方式・生成族・公開GraphML・代表図")
    + validation.details("topology", "方向の統制とSCC固定。全条件の図表")
    + validation.details("public", "元から有向の公開データ。入力と再試行の明細")
    + validation.details("budget", "平面・放射・dot・トーラスを同じ時計予算で再比較"))
    leveling = section("leveling", "2. 層数探索と層割当", """
<p>左右境界を通る元辺数を先に抑え、その数を達成できる最小層数を二分探索する。全候補の厳密値と90/90件で一致し、求解回数を平均8.61回削減した。固定層数案に比べ64組中51組で通過元辺が減り、平均−5.03本、層数は平均＋4.36層。固定案は8件で実行不能だった。</p>
<p>同じ層数と通過元辺数で、線形・二乗和・QP・重心方式などを比較した。二乗和では対象のスパン二乗和を改善したが、完成図の交差は初回で平均＋0.13、追試で＋0.88。層を増やす対照も改善と悪化が混在した。低予算の二次モデルに実行可能初期解を渡すと、解ありは14/16件から16/16件に改善。低予算で最適終了はどちらも13件だった。</p>
<p>UKfacultyの未完走例では14層で33本を最適と確認した後、7層では8秒で実行可能解がなく、読み出しで停止した。保存した下界は43本なので、7層で目標33本は達成不能と判断できる。未確定の終了状態を扱えるようにし、下界を判定に使う修正点が明らかになった。</p>
""" + initial.details("layering") + validation.details("ranks"))
    subdiv = section("subdivision", "3. 長辺の分割", """
<p>同じ割当で各端点を探索する旧版と、頂点から層への索引を使う現行版を比較した。初回72/72件で全出力が一致し、単位スパンと予測ダミー数も一致した。長辺を増やした追試では50・200・800頂点で各9反復、全27試行で同じ結果だった。800頂点では中央値156.23 msから99.07 msへ短縮した。</p>
<p>800頂点の例は分割後にダミー140,426個、線分142,826本。索引は挿入を速くするが、後段が処理するグラフの大きさは残る。時間の説明には元の頂点数と分割後の線分数・最大層幅の両方が必要である。</p>
""" + initial.details("subdivision")
    + '<p class="key-source">' + link(f"../{VALIDATION}/subdivision/results.csv", "長辺ストレスの生データ") + "</p>")
    crossing = section("crossing", "4. 層内順序・交差・切れ目", """
<p>円形重心は初期交差を平均141.19減らし、sifting後にも平均6.49の差が残った。siftingは初期化だけより平均9.86交差減らし、全体最良状態を残すguard付きはguardなしより37組で少なかった。5回と10回は72件すべて同値。追試では1回と5回で15/16件が同値、4開始で5/16件に改善があった。4開始の総探索時間は平均0.334秒増えた。</p>
<p>巻き数0の小規模全列挙ではsiftingが32/40件で最適値と一致、最大差4。巻き数±1の全列挙では自由化で9/20件の厳密値が改善し、自由siftingは20件でその値に一致した。ただし19件が交差0の小問題だった。別途、2層構成では異なる帯の辺を局所的に交差として数える実装上の問題が再現した。</p>
<p>回転は角度変位を平均で減らしたが、21/72件で増えた。切れ目DPは線分数について厳密列挙と初回40/40件、人工ストレス36/36件で一致した。既定UNWIND＋DPはDP単独より通過線分が21/72件で多かった。DP単独候補を加えると既定より初回5/24件、追試2/28件で減り、交差は変わらなかった。長辺・複数巻きの人工例では36件中2件で、通過線分数と通過元辺数の最少値を与える切れ目が異なった。</p>
""" + geom + initial.details("crossing") + initial.details("oracles")
    + validation.details("winding") + validation.details("seams"))
    coordinates = section("coordinates", "5. 座標割当と計測の監査", f"""
<p>初回ではBKの4回平滑化で70/72件の総辺長が減り、62/72件で曲がりが増えた。射影を外した対照の61/72件は範囲または順序に違反。競合マーク、整列、圧縮、方向統合の個別比較では、曲がりと辺長の効果が異なった。</p>
<p>最小周期で曲がり重み1のLPは、既定BKより16/16件で曲がりを減らした。辺長は8件ずつ短縮・増加。重み4では曲がりがさらに減り、辺長は重み1より平均1.21増えた。QPは初回の72件中12件で求解エラー。3×3 BKは同周期BKより曲がりが追試で平均8.69減ったが、総辺長は16/16件で増加。初回72件中12件で、有限な展開範囲のため中央から出る線分もBKの配置計算から抜けた。</p>
<p>固定埋め込みの144条件で、層順・巻き数による交差数と独立したリフト上の計数が一致した。丸めとクリッピングを使う汎用計測器はLP系9条件で−1〜＋2ずれた。座標の評価は交差の微差を除き、妥当な描画範囲で測った曲がりと辺長を使う。</p>
<p class="caution">拡張周期では、LPと描画が異なる上下端を使う。描画入口まで再現した監査ではLPの{invalid}/64条件が範囲エラーで、最小周期のLPは32/32条件が通った。拡張周期は実験用の指定で、現行の通常LPは最小周期を使う。過去の拡張周期LP表は記録として収録し、方式選択の結論から外した。</p>
""" + bounds + initial.details("coordinates") + details("追試の座標条件・曲がりと辺長・独立計数", followup)
    + '<p class="key-source">' + link("../bk_3x3_experiment/comparison.json", "初期の3入力による3×3比較")
    + " · " + link("../../documents/bk_3x3_experiment.md", "実装と周期整合性の技術メモ") + "</p>")
    runtime = section("runtime", "6. 規模・計算時間・完走率", """
<p>初回の規模比較は112試行中68完走。エラー43件のうち40件は二次目的の調整モデルで求解開始前のサイズ制限、残る3件は実行可能解なしの読み出しで発生した。worker自体の時間切れも1件あった。追試で二次モデルは90・120頂点の4入力で制限エラー10010。線形分配と1回設定では36–120頂点の8/8条件で描画座標まで完了し、2件は制限付き上流解を含む。</p>
<p>完走68件では交差削減が54件で最も遅く、中央値1.060秒。層探索0.134秒、層調整0.026秒、座標割当0.005秒。120頂点のDAGでは1回設定でも交差削減に5.06秒。層局所の変更後に全体交差を再計数するため、層間の辺索引と差分更新が実装の主要な改善箇所である。この計測は漸近計算量の推定には使わない。</p>
<p>共通24秒の再比較ではトーラス、dot、平面杉山が12/12件、放射型が6/12件完走。放射型の品質差は完走組の結果である。WLSはホスト名解決で止まり、フルライセンスでの既定法の規模は未測定。</p>
""" + initial.details("scaling") + validation.details("scaling")
    + '<p class="key-source">' + link(f"../{VALIDATION}/wls_escalated/rows.jsonl", "WLSの再確認記録") + "</p>")
    drawing = section("drawing", "7. 周期描画", """
<p>最初の境界分割7例と交差判定4例が期待値と一致した。境界を同時にまたぐ角、複数巻き、矢印が最終端に一つ付くことを含む。追試の人工36例では、層切れ目の回転と全体の平行移動でも交差計数が保存された。画像4組では周辺を表示すると容量中央値が約34 KBから92 KBに増えた。</p>
""" + initial.details("drawing") + validation.details("validation", "追加の境界不変性と長辺挿入の全結果"))
    review = section("review", "8. 実装上の問題と修正順", """
<p>まず層割当の終了処理と二分探索、2層交差を修正する。続いて切れ目の候補選択、座標・描画・計測の基本領域の整合を直す。その後に交差削減の差分計数を計測し、同じ入力で既定の探索予算と座標方式を再評価する。</p>
<p>確認済みの挙動と、その証拠に基づく修正候補を下表に記録した。今回の統合と監査で描画のアルゴリズムは変更していない。</p>
""" + implementation_review()
    + '<p class="key-source">' + link("audits/two_layer_crossing.json", "2層の入力と計数結果")
    + " · " + link("audits/drawing_domain.csv", "描画範囲の全144試行")
    + " · " + link("audits/settings.json", "再現監査の設定") + "</p>")
    conclusion = section("conclusion", "9. 結論と適用範囲", """
<p><strong>支持されたこと。</strong> 円環沿いの方向に対する交差削減、平面杉山比での逆行辺減少、二方向の周期を使う内部効果、切れ目DPの線分最適性、索引化したダミー挿入での同一出力が、計算実験で確認できた。</p>
<p><strong>条件に依存すること。</strong> 元の向きでの公開ネットワークでは交差が増加した。曲がり、辺長、境界通過は目的関数や周期によって別々に変わる。</p>
<p><strong>推定の限界。</strong> 公開の有向標本は3集合で、時点・誘導部分グラフ間に重複がある。放射型では欠測が多く、幾何交差は中心線の近似に依存する。WLSが未接続で、規模の大きい既定法と通常の5回設定での120頂点は未検証である。</p>
""")
    sources = section("data", "付録　実験条件・生データ・再現手順", """
<p>結果は2026年11月20日（日本時間）の測定を基にした。主な環境はPython 3.13.0、Gurobi 13.0.0、Graphviz 16.1.1。グループによってソルバー・worker上限と並行数が異なる。各設定のソースSHAと版を照合できる。行数には、同じグラフの条件、前処理、打ち切りを含む。</p>
""" + details("全グループの設定・入力・測定行と状態", inventory(initial, validation))
    + initial.details("methods", "初回の実行条件と集計方法")
    + initial.details("followup", "初回所見を受けた3件の追加実験")
    + validation.details("overview", "追試15グループの実験台帳")
    + f'<p class="key-source">{link(f"../{INITIAL}/index.html", "初回HTML")} · {link(f"../{VALIDATION}/index.html", "追試HTML")} · {link("../../documents/experiment_validation.md", "追試の再実行手順")} · {link(f"../{INITIAL}/benchmark_sources/provenance.json", "初回の公開データ出典")} · {link(f"../{VALIDATION}/sources/provenance.json", "追試の公開データ出典")}</p>'
    + """<h3>統合版の再生成</h3>
<p>実験リポジトリのルートから実行する。上のCSV・JSONLの再利用で本文を生成できる。再現監査を測り直す場合は、先に監査スクリプトを実行する。</p>
<pre><code>MPLBACKEND=Agg MPLCONFIGDIR=/tmp/torus-study-mpl PYTHONHASHSEED=0 PYTHONPATH=src \
  ./theme2026-saku/bin/python experiments/audit_torus_report.py output/torus_complete_20261120/audits
MPLCONFIGDIR=/tmp/torus-study-mpl ./theme2026-saku/bin/python \
  experiments/report_torus_complete.py output/torus_complete_20261120</code></pre>""")
    blocks = (summary, method, framework, leveling, subdiv, crossing,
              coordinates, runtime, drawing, review, conclusion, sources)
    navigation = (
        ("summary", "要旨"), ("methods", "方法・文献"), ("framework", "全体比較"),
        ("leveling", "層割当"), ("subdivision", "長辺の分割"), ("crossing", "交差・境界"),
        ("coordinates", "座標"), ("runtime", "性能"), ("drawing", "描画"),
        ("review", "実装修正"), ("conclusion", "結論"), ("data", "生データ"),
    )
    nav = "".join(f"<li>{link('#' + anchor, title)}</li>" for anchor, title in navigation)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title><style>{STYLE}{EXTRA_STYLE}</style></head>
<body><a class="skip" href="#main">本文へ移動</a>
<header><p class="date">2026年11月20日</p><h1>{TITLE}</h1>
<p>平面・放射・dotとの比較から、層割当、交差、切れ目、座標、描画までの評価。</p>
<div class="actions">{link("#summary", "要旨を読む")} {link("#data", "実行条件と生データ")}</div></header>
<nav aria-label="目次"><ul>{nav}</ul></nav>
<main id="main">{"".join(blocks)}</main>
<footer><p>{link("#main", "本文の先頭へ")}</p></footer></body></html>
"""


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (args.output / "index.html").write_text(build(args.output), encoding="utf-8")


if __name__ == "__main__":
    main()
