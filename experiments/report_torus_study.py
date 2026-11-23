"""Build an offline Japanese HTML report from the measured torus study results."""

import argparse
from collections import Counter
import csv
from html import escape
import json
import math
from pathlib import Path
from statistics import mean, median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run_torus_study import bootstrap

BLUE = "#176a9b"
ORANGE = "#9a471e"
INK = "#16324a"
TEAL = "#087d73"
COLORS = (BLUE, TEAL, ORANGE, "#70539b", "#b0810d")
FAMILIES = ("dag", "random", "scc_chain", "watts_strogatz")
LABELS = {"dag": "DAG", "random": "Random", "scc_chain": "SCC chain", "watts_strogatz": "Watts–Strogatz",
          "att": "AT&T / North", "rome": "Rome（有向化）", "dagmar": "RandDAG",
          "torus": "トーラス", "sugiyama": "平面杉山", "radial": "放射型", "dot": "Graphviz dot",
          "cylindrical_reference": "円筒対照", "torus_without_unwind_or_dp": "UNWIND・DP なし",
          "case_timeout": "worker 時間切れ", "error": "実行エラー", "no_solution": "解なし",
          "license_size_limit": "ライセンスの規模上限",
          "invalid_assignment": "制約違反", "invalid_coordinates": "座標違反",
          "unproven": "最適性未確定", "ok": "完了"}
STYLE = """
:root{color-scheme:light;--ink:#16324a;--text:#273d50;--muted:#4d6474;--line:#d5e1e8;
--paper:#fff;--background:#f3f7f9;--blue:#0b5e86;--teal:#076e64;--warm:#883b14}
*{box-sizing:border-box}
html{font-family:system-ui,"Hiragino Sans","Yu Gothic",sans-serif;background:var(--background);
color:var(--text);line-height:1.7}
body{margin:0}
a{color:var(--blue);text-underline-offset:.17em;overflow-wrap:anywhere}
a:focus-visible,[tabindex]:focus-visible,summary:focus-visible{outline:3px solid #007289;outline-offset:4px}
.skip{position:absolute;top:4px;left:4px;padding:.5rem;background:white;transform:translateY(-150%)}
.skip:focus{transform:translateY(0)}
header{background:#112f45;color:#eef8fb;padding:clamp(2rem,6vw,5rem) max(1.15rem,calc((100vw - 72rem)/2));}
header p{max-width:57rem;color:#d7eaf4;margin:.9rem 0 0}
h1,h2,h3{line-height:1.38;color:var(--ink)}
h1{color:white;margin:.3rem 0;font-size:clamp(1.85rem,5vw,3.6rem)}
h2{font-size:clamp(1.35rem,3vw,2rem);margin:.15rem 0 1.05rem}
h3{margin:1.6rem 0 .5rem;font-size:1.16rem}
header .date{font:700 .87rem/1.4 system-ui;letter-spacing:.1em;color:#93e0d1}
main,footer,nav{max-width:74rem;margin:0 auto;padding-inline:1rem}
nav{margin-block:1.3rem}
nav ul{margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.47rem;list-style:none}
nav a{display:block;padding:.34rem .75rem;border:1px solid var(--line);border-radius:.5rem;background:white}
section{background:var(--paper);border:1px solid var(--line);border-radius:.85rem;
padding:clamp(1rem,3vw,2rem);margin:0 0 1.15rem;scroll-margin:1rem}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr));gap:.8rem;margin:1rem 0}
.card{background:#edf6f7;border:1px solid #cbdede;border-radius:.6rem;padding:.75rem 1rem}
.card strong{font-size:1.4rem;display:block;color:var(--ink)}
.note{background:#eaf5f8;border-inline-start:4px solid #277597;padding:.65rem 1rem}
.caution{background:#fff4ea;border-inline-start:4px solid #a75b2c;padding:.65rem 1rem}
.table-wrap{overflow:auto;margin:.9rem 0 1.35rem;border:1px solid var(--line);border-radius:.5rem;}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.92rem}
caption{text-align:start;padding:.55rem .7rem;font-weight:700;color:var(--ink);background:#e9f2f6}
th,td{padding:.5rem .65rem;vertical-align:top;text-align:end;border-bottom:1px solid var(--line)}
th{font-weight:650;color:var(--ink)}
thead th{background:#f4f8f9}
th:first-child,td:first-child{text-align:start;overflow-wrap:anywhere}
tbody tr:nth-child(even){background:#f7fafb}
td:last-child,th:last-child{border-inline-end:0}
figure{margin:1rem 0;padding:.75rem;border:1px solid var(--line);border-radius:.55rem;}
figure img{width:100%;height:auto;display:block;margin:0 auto;max-width:65rem}
figcaption{margin-top:.65rem;color:var(--muted);font-size:.92rem}
.examples{display:grid;gap:.75rem;grid-template-columns:repeat(auto-fit,minmax(min(100%,15rem),1fr))}
.examples figure{margin:0}
details{margin:1rem 0}
summary{cursor:pointer;font-weight:700;color:var(--blue)}
code{font-family:ui-monospace,monospace;font-size:.9em;overflow-wrap:anywhere}
footer{padding-bottom:2rem;color:var(--muted)}
@media print {header{background:white;color:var(--ink);padding:1rem}h1,header p,header .date{color:var(--ink)}
nav,.skip{display:none}html{background:white}figure,table{break-inside:avoid}section{border:none}}
"""


def label(key):
    return LABELS.get(key, key)


def fmt(value, digits=2):
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.{digits}f}"


def table(caption, headers, rows):
    values = []
    for row in rows:
        cells = [f'<th scope="row">{escape(fmt(row[0]))}</th>']
        cells.extend(f"<td>{escape(fmt(value))}</td>" for value in row[1:])
        values.append("<tr>" + "".join(cells) + "</tr>")
    headings = "".join(f'<th scope="col">{escape(value)}</th>' for value in headers)
    return (f'<div class="table-wrap" tabindex="0" role="region" aria-label="{escape(caption)}">'
            f'<table><caption>{escape(caption)}</caption><thead><tr>{headings}</tr></thead>'
            f'<tbody>{"".join(values)}</tbody></table></div>')


def figure(path, alt, caption):
    return (f'<figure><img src="{escape(path)}" alt="{escape(alt)}" loading="lazy">'
            f'<figcaption>{escape(caption)}</figcaption></figure>')


def section(identifier, title, content):
    return f'<section id="{identifier}"><h2>{title}</h2>{content}</section>'


def read_rows(root, name):
    path = root / name / "rows.jsonl"
    if not path.exists():
        return []
    # A killed worker may have left the last write incomplete.
    return [json.loads(line) for line in path.read_text().splitlines(keepends=True) if line.endswith("\n")]


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def values(rows, exp, method, field, where=lambda r: True):
    return {r["case"]: r[field] for r in rows if r["experiment"] == exp and r["variant"] == method
            and r["status"] == "ok" and r.get(field) is not None and where(r)}


def paired(rows, exp, treatment, control, field, where=lambda r: True):
    a = values(rows, exp, treatment, field, where)
    b = values(rows, exp, control, field, where)
    return [(case, a[case], b[case]) for case in sorted(a.keys() & b.keys())]


def tolerance(delta):
    return 0 if abs(delta) <= 1e-8 else (1 if delta > 0 else -1)


def stat_line(description, pairs):
    if not pairs:
        return description, 0, None, None, None, "—"
    diff = [a - b for _, a, b in pairs]
    lo, hi = bootstrap(diff, 2000)
    interval = f"[{fmt(lo)}, {fmt(hi)}]"
    counts = Counter(tolerance(x) for x in diff)
    return description, len(diff), mean(diff), median(diff), interval, f"{counts[-1]} / {counts[0]} / {counts[1]}"


def pair_table(caption, lines):
    return table(caption, ("差の定義（左 − 右）", "対応数", "平均差", "中央値", "平均差 95%区間", "減 / 同 / 増"), lines)


def results_table(caption, rows, exp, methods, metrics):
    result = []
    for method in methods:
        subset = [r for r in rows if r["experiment"] == exp and r["variant"] == method]
        ok = [r for r in subset if r["status"] == "ok"]
        cells = []
        for field, _ in metrics:
            data = [r[field] for r in ok if isinstance(r.get(field), (int, float))]
            cells.append(median(data) if data else None)
        limited = sum(bool(r.get("solver_limited") or r.get("input_solver_limited")) for r in ok)
        result.append((label(method), f"{len(ok)}/{len(subset)}", limited, *cells))
    return table(caption, ("方式", "完了 / 試行", "制限付き完了", *(name for _, name in metrics)), result)


def style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#b5c4cf")
    ax.tick_params(colors=INK)
    ax.grid(axis="y", color="#e1e9ef", linewidth=.8, zorder=0)
    ax.set_axisbelow(True)


def save(fig, root, name):
    path = root / "charts" / f"{name}.png"
    path.parent.mkdir(exist_ok=True)
    fig.savefig(path, dpi=155, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return f"charts/{path.name}"


def difference_chart(root, name, items, axis_label):
    fig, ax = plt.subplots(figsize=(8.4, max(2.3, .49*len(items) + .8)), layout="constrained")
    style_axes(ax)
    ax.axvline(0, color="#596b78", linewidth=1, zorder=1)
    for index, (text, sample) in enumerate(items):
        if not sample:
            continue
        diff = [a-b for _, a, b in sample]
        avg = mean(diff)
        low, high = bootstrap(diff, 2000)
        color = TEAL if avg <= 0 else ORANGE
        if low is not None:
            ax.hlines(index, low, high, linewidth=2, color=color, zorder=3)
        ax.scatter(avg, index, color=color, s=43, edgecolor="white", linewidth=.5, zorder=4)
    ax.set_yticks(range(len(items)), [f"{text} (n={len(sample)})" for text, sample in items])
    ax.invert_yaxis()
    ax.set_xlabel(axis_label)
    ax.grid(axis="x", color="#e1e9ef", linewidth=.8, zorder=0)
    ax.grid(axis="y", visible=False)
    return save(fig, root, name)


def framework_plot(root, rows):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), layout="constrained")
    for ax, baseline, title in zip(axes, ("sugiyama", "dot"), ("Repository Sugiyama", "Graphviz dot")):
        maximum = 1
        for i, family in enumerate(FAMILIES):
            pair = paired(rows, "framework", "torus", baseline, "geometric_crossings",
                          lambda r: r["family"] == family)
            if pair:
                ax.scatter([b for _, _, b in pair], [a for _, a, _ in pair], s=23, alpha=.78,
                           label=f"{label(family)} ({len(pair)})", color=COLORS[i], marker=("o","s","^","D")[i])
                maximum = max(maximum, *(max(a, b) for _, a, b in pair))
        ax.plot([0, maximum], [0, maximum], "--", color="#718795", lw=1)
        ax.set(xlabel="Baseline crossings", ylabel="Torus crossings", title=title)
        style_axes(ax)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(loc="upper left", frameon=False, fontsize=7)
    return save(fig, root, "framework")


def profile_plot(root, rows):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), layout="constrained")
    for i, family in enumerate(FAMILIES):
        family_rows = [r for r in rows if r["family"] == family]
        sizes = sorted({r["nodes"] for r in family_rows})
        valid = [[r for r in family_rows if r["nodes"] == n and r["status"] == "ok"] for n in sizes]
        fractions = [len(v)/sum(r["nodes"] == n for r in family_rows) for n, v in zip(sizes, valid)]
        times = [median([r["layout_seconds"] for r in v]) if v else math.nan for v in valid]
        for ax, series in zip(axes, (fractions, times)):
            ax.plot(sizes, series, label=label(family), marker=("o","s","^","D")[i], color=COLORS[i])
    axes[0].set(xlabel="Original vertices", ylabel="Completed fraction", ylim=(-.05, 1.07))
    axes[1].set(xlabel="Original vertices", ylabel="Median wall time (s)", yscale="log")
    for ax in axes:
        style_axes(ax)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(frameon=False, fontsize=8)
    return save(fig, root, "scaling")


def bar_plot(root, name, rows, exp, methods, fields):
    fig, axes = plt.subplots(1, len(fields), figsize=(max(5.6, 4.9*len(fields)), 3.5),
                             layout="constrained", squeeze=False)
    for ax, (field, title) in zip(axes[0], fields):
        groups = [list(values(rows, exp, method, field).values()) for method in methods]
        if any(groups):
            ax.boxplot(groups, orientation="vertical", patch_artist=True,
                       boxprops={"facecolor":"#d0e8ec","edgecolor":TEAL},
                       medianprops={"color":INK, "linewidth":1.5},
                       flierprops={"marker":"o","markersize":3,"alpha":.4})
        ax.set_xticks(range(1, 1+len(methods)), methods, rotation=23, ha="right", fontsize=8)
        ax.set_ylabel(title)
        style_axes(ax)
    return save(fig, root, name)


def framework_section(root, synthetic, benchmark):
    def block(rows, name):
        variants = ("torus", "sugiyama", "radial", "dot", "cylindrical_reference", "torus_without_unwind_or_dp")
        absolute = results_table(f"{name}の完走数と代表値（完走分の中央値）", rows, "framework", variants, (
            ("geometric_crossings", "幾何交差"), ("overlapping_edge_pairs", "重なり辺対"),
            ("reverse_direction_edges", "逆行辺"), ("either_seam_edges", "境界を通る元辺"),
            ("bends", "曲がり"), ("length_per_frame_diagonal", "正規化総辺長"),
            ("layout_seconds", "時間 (s)"),
        ))
        pairs = [
            stat_line(f"トーラス − {label(baseline)}／{name}", paired(rows, "framework", "torus", baseline,
                                                                     "geometric_crossings"))
            for baseline in ("sugiyama", "radial", "dot", "cylindrical_reference",
                             "torus_without_unwind_or_dp")
        ]
        return absolute + pair_table(f"{name}での幾何交差数の対応差", pairs)

    scatter = framework_plot(root, synthetic)
    comparison = [
        stat_line(f"{label(family)}／{label(baseline)}", paired(
            synthetic, "framework", "torus", baseline, "geometric_crossings",
            lambda r: r["family"] == family))
        for family in FAMILIES for baseline in ("sugiyama", "dot")
    ]
    benchmark_comparison = [
        stat_line(f"{label(family)}／{label(baseline)}", paired(
            benchmark, "framework", "torus", baseline, "geometric_crossings",
            lambda r: r["family"] == family))
        for family in ("att", "rome", "dagmar") for baseline in ("sugiyama", "dot")
    ]
    return section("framework", "1. フレームワーク全体", '''
<p>同じ有向グラフを各方式で描き、出来上がった辺の中心線を共通の測定器で数えた。円筒対照では層内方向の巻き数を 0 に固定した。UNWIND・DP なしの条件は境界処理の追加効果を調べるためのもの。平面・放射型の閉路除去で反転した辺は描画時に元の向きに戻るが、階層方向には逆行する。</p>
''' + figure(scatter, "平面杉山法・Graphvizとトーラスの幾何交差の散布図。斜線より上はトーラスの交差が多い。",
             "図 1。1 点は同じ入力の 1 対。斜線より下ではトーラスの幾何交差が少ない。方式によって完走した入力が異なるため、対応数は下表で確認できる。")
        + '<h3>統制生成グラフ</h3>' + block(synthetic, "統制生成")
        + pair_table("統制生成でのグラフ族別の対応差", comparison)
        + '<h3>公開グラフの小標本</h3><p>研究者の公開ミラーに収録された AT&amp;T / North、Rome、RandDAG から、取得できた 10・12・16・20・24 頂点の候補を各サイズ最大 2 件ずつ測定した。掲載リストから SHA 順に抽出した探索的標本で、全コレクションの代表性は評価していない。旧形式の方向指定はコレクションの属性から補った。Rome は各辺を固定 seed で有向化した。<a href="https://github.com/VisDunneRight/benchmark_sets_analysis_data">データミラー</a> · <a href="benchmark_sources/provenance.json">元ファイル URL と Git blob SHA</a></p>'
        + block(benchmark, "公開標本")
        + pair_table("公開標本でのグラフ族別の対応差", benchmark_comparison))


def layer_section(root, rows):
    groups = [
        ("二分探索 − 固定層数／左右通過辺", "search", "binary", "fixed_sqrt", "rank_wrap_edges"),
        ("二分探索 − 固定層数／層数", "search", "binary", "fixed_sqrt", "layers"),
        ("二乗和 − 総和／スパン二乗和", "balance", "diff_square", "diff", "span_square_sum"),
        ("二乗和 − 総和／総スパン", "balance", "diff_square", "diff", "span_sum"),
        ("二乗和 − 総和／最長スパン", "balance", "diff_square", "diff", "max_span"),
        ("二乗和 − 総和／完成図の交差", "balance_downstream", "diff_square", "diff", "geometric_crossings"),
        ("既定 − 固定層数／完成図の交差", "layering_downstream", "default", "fixed_sqrt", "geometric_crossings"),
        ("2 倍層数 − 既定／完成図の交差", "layering_downstream", "double_layers", "default", "geometric_crossings"),
    ]
    lines = [stat_line(title, paired(rows, exp, a, b, field)) for title, exp, a, b, field in groups]
    chart = bar_plot(root, "layering", rows, "balance", ("feasible","diff","diff_square","qp","barycenter"),
                     (("span_square_sum", "Sum of squared spans"), ("max_span", "Maximum span")))
    return section("layering", "2. 階層数探索と分配", '''
<p>二分探索はまず左右境界を通る元辺の目標数を定め、それを達成する最小層数を探す。固定案には ceil(√(2n)) 層を与えた。分配の比較では同じ層数と通過辺数を固定し、追加最適化なし、総和、二乗和、QP、重心法を比較した。固定案で解が得られなかった入力は試行数に残し、完成図の対応差からは外した。</p>
''' + figure(chart, "5方式についてスパン二乗和と最大スパンの分布を表示する箱ひげ図。",
             "図 2。箱は中央 50%、中央線は中央値。方式によって完走したグラフが異なるので、判断には下の対応差を併用する。")
        + results_table("階層数探索", rows, "search", ("binary", "fixed_sqrt"), (
            ("layers","層数"), ("rank_wrap_edges","左右通過辺"), ("solver_calls","求解回数"), ("wall_seconds","時間 (s)")))
        + results_table("層数と通過辺数を固定した分配", rows, "balance",
            ("feasible", "diff", "diff_square", "qp", "barycenter"), (
            ("span_sum","総スパン"), ("span_square_sum","二乗和"), ("max_span","最大スパン"),
            ("predicted_dummies","予測ダミー数"), ("wall_seconds","時間 (s)")))
        + results_table("階層割当全体", rows, "layering_step", ("default", "fixed_sqrt", "double_layers"), (
            ("layers","層数"), ("rank_wrap_edges","左右通過辺"), ("span_sum","総スパン"),
            ("layer_step_seconds","探索＋分配時間 (s)")))
        + pair_table("工程内の指標と完成描画の対応差", lines))


def subdivision_section(rows):
    checks = [r for r in rows if r["experiment"] == "subdivision_checks" and r["status"] == "ok"]
    audit = []
    for variant in ("current_lookup", "explicit_empty_layers"):
        data = [r for r in checks if r["variant"] == variant]
        audit.append((variant, len(data), sum(r["matches_legacy"] for r in data),
                      sum(r["dummy_count_matches_rank_span"] for r in data),
                      sum(r["unit_span_violations"] > 0 for r in data),
                      median([r["dummy_nodes"] for r in data]) if data else None))
    speeds = [stat_line(f"{a} − {b}／時間 (s)",
                        paired(rows,"subdivision",a,b,"wall_seconds"))
              for a,b in (("current_lookup","legacy_lookup"),("explicit_empty_layers","current_lookup"))]
    return section("subdivision", "3. ダミー頂点の挿入", '''
<p>階層割当を固定し、各辺の端点が属する階層を全探索する旧法と、頂点→階層の索引を使う現行法を比較した。同じ入力層の比較では頂点列・辺列・層・巻きフラグ・重みの完全一致を調べた。各元辺の経路が連続し、分割後の各線分が階層方向に一つ進むことも検査した。</p>
''' + table("分割の正しさ", ("方式", "検査数", "旧出力と完全一致", "Σ(s−1) と一致",
                              "単位スパン違反ケース", "ダミー数の中央値"), audit)
        + pair_table("分割時間の対応差", speeds))


def crossing_section(root, rows):
    layer = [
        ("Circular barycenter", "circular_barycenter", "input_order", "initialization"),
        ("Barycenter + same sifting", "circular_barycenter", "input_order", "initialization_then_sifting"),
        ("Guarded sifting", "default", "no_sifting", "sifting"),
        ("Guard effect", "default", "no_guard", "sifting"),
        ("Variable winding", "default", "fixed_winding", "sifting"),
    ]
    cuts = [("Rotation", "guarded", "off", "rotation"), ("Unwind", "full", "off", "unwind"),
            ("Greedy cut", "greedy", "off", "seam"), ("DP cut", "dp", "off", "seam"),
            ("Early and late vs. early", "early_and_late", "unwind_first_only", "unwind_dp_order"),
            ("Unwind + DP", "unwind_1_dp_1", "unwind_0_dp_0", "crossing_step")]
    chart = difference_chart(root, "seam", [(
        title, paired(rows, exp, a, b, "seam_segments")) for title,a,b,exp in cuts], "Change in y-seam segments")
    step_parts = (
        ("initialization", ("input_order","circular_barycenter")),
        ("sifting", ("no_sifting","rounds_1","default","rounds_10","no_guard","fixed_winding")),
        ("rotation", ("off","unguarded","guarded")),
        ("unwind", ("off","inner_only","full")),
        ("seam", ("off","greedy","dp")),
    )
    details = "".join(results_table(exp, rows, exp, variants, (
        ("embedding_crossings","工程内交差"), ("inner_segment_crossings","内部線分交差"),
        ("angular_span_sum","角度変位の総和"), ("seam_segments","上下通過線分"),
        ("algorithm_seconds","時間 (s)"))) for exp, variants in step_parts)
    return section("crossing", "4. 交差削減と境界処理", '''
<p>分割グラフを固定し、円形重心で初期化し、同じ入力から sifting の有無・回数・guard・巻き数の自由度を変更した。次に回転、層間の共通巻きを引く UNWIND、上下境界を通る線分の本数を最小化する切れ目 DP を比較した。回転の角度変位は一周を 1 とし、上下通過線分と幾何交差は個別に測った。</p>
''' + pair_table("初期化と sifting が工程内交差に与えた影響", [
            stat_line(a,paired(rows,exp,t,b,"embedding_crossings")) for a,t,b,exp in layer])
        + figure(chart, "各境界処理による上下境界通過線分数の対応差と95%区間。",
                 "図 3。左側ほど処理後に上下境界を通る線分が減った。点は平均差、線はケースを単位とする bootstrap 95% 区間。")
        + pair_table("境界処理による上下通過線分数の対応差", [
            stat_line(a,paired(rows,exp,t,b,"seam_segments")) for a,t,b,exp in cuts])
        + results_table("交差削減工程全体の 2×2 比較", rows, "crossing_step",
            ("unwind_0_dp_0","unwind_1_dp_0","unwind_0_dp_1","unwind_1_dp_1"), (
            ("geometric_crossings","幾何交差"), ("y_seam_segments","上下通過線分"),
            ("y_seam_edges","上下通過元辺"), ("total_edge_length","総辺長"),
            ("algorithm_seconds","時間 (s)")))
        + pair_table("両処理を追加したときの図への影響", [
            stat_line(name,paired(rows,"crossing_step","unwind_1_dp_1","unwind_0_dp_0",field))
            for name,field in (("幾何交差","geometric_crossings"),("上下通過元辺","y_seam_edges"),
                               ("総辺長","total_edge_length"),("工程時間 (s)","algorithm_seconds"))])
        + pair_table("交差削減工程全体での上下通過線分数の対応差", [
            stat_line(name,paired(rows,"crossing_step",left,right,"seam_segments"))
            for name,left,right in (("DP だけ − 両方なし","unwind_0_dp_1","unwind_0_dp_0"),
                                   ("UNWIND だけ − 両方なし","unwind_1_dp_0","unwind_0_dp_0"),
                                   ("両方あり − DP だけ","unwind_1_dp_1","unwind_0_dp_1"))])
        + f"<details><summary>初期化・sifting・回転・UNWIND・DPの全条件</summary>{details}</details>")


def coordinate_section(root, rows):
    variants = ("uniform","uniform_smooth","bk_no_smooth","bk","bk_smooth_10","qp","lp","lp_bend_1","bk_3x3")
    chart = bar_plot(root, "coordinates", rows, "coordinates", variants,
                     (("bends","Bends per layout"), ("total_edge_length","Total edge length")))
    comps = (
        ("周期平滑化／総辺長", "bk","bk_no_smooth","total_edge_length"),
        ("周期平滑化／曲がり", "bk","bk_no_smooth","bends"),
        ("周期平滑化／整列内部線分", "bk","bk_no_smooth","aligned_inner_segments"),
        ("LP − 既定 BK／総辺長", "lp","bk","total_edge_length"),
        ("LP − 既定 BK／曲がり", "lp","bk","bends"),
        ("曲がりペナルティ付き LP − LP／曲がり", "lp_bend_1","lp","bends"),
        ("3×3 BK − 既定 BK／曲がり", "bk_3x3","bk","bends"),
        ("3×3 BK − 既定 BK／周期", "bk_3x3","bk","period"),
    )
    internals = "".join(results_table(exp, rows, exp, methods, (
        ("order_violations","順序違反"), ("gap_violations","最小間隔違反"),
        ("domain_violations","周期領域外"), ("bends","曲がり"),
        ("algorithm_seconds","時間 (s)")))
        for exp, methods in (("bk_merge", ("direction_0","direction_1","direction_2","direction_3","median")),
                             ("bk_projection", ("off","on")),
                             ("bk_components", ("all","no_conflict_marking","no_alignment","equal_spacing_instead_of_compaction"))))
    projection = [r for r in rows if r["experiment"] == "bk_projection" and r["variant"] == "off"]
    failures = sum(r["status"] == "invalid_coordinates" for r in projection)
    replica = [r for r in rows if r["experiment"] == "coordinates" and r["variant"] == "bk_3x3" and r["status"] == "ok"]
    omitted = sum(r.get("central_source_segments_omitted", 0) > 0 for r in replica)
    return section("coordinates", "5. 座標の割当と内部処理", f'''
<p>層、層内順序、巻き数を固定した。辺長と曲がりは周期境界で図を切る前の折れ線から求めた。3×3 BK は隣接タイルを含めて配置し、中央タイルの座標と必要な周期を取り出す。中央から出発して 3×3 範囲外に抜けるためにコピー計算から落ちた線分があったのは {omitted}/{len(replica)} 件。既定 BK と 3×3 BK の周期差を調べるため、後述の同一周期の追加比較も実施した。</p>
''' + figure(chart,"座標方式別の曲がりと総辺長の箱ひげ図。",
              "図 4。曲がりの少なさと辺長を別軸で示す。特に 3×3 BK の辺長には、変更後の周期が反映される。")
        + results_table("座標方式ごとの完走と中央値",rows,"coordinates",variants,(
            ("total_edge_length","総辺長"), ("bends","曲がり"), ("aligned_inner_segments","整列内部線分"),
            ("period","周期"), ("gap_violations","間隔違反"), ("algorithm_seconds","時間 (s)")))
        + pair_table("座標方式の対応差", [stat_line(n,paired(rows,"coordinates",a,b,f)) for n,a,b,f in comps])
        + f'<p class="note">射影を外した対照では {failures}/{len(projection)} 件で領域または順序に違反した。比較のために意図的に外した条件の結果である。</p>'
        + f"<details><summary>単方向BK・競合マーク・整列・圧縮・射影の全条件</summary>{internals}</details>")


def oracle_section(rows):
    binary = [r for r in rows if r["experiment"] == "search_oracle" and r["variant"] == "binary"]
    exact = [r for r in rows if r["experiment"] == "search_oracle" and r["variant"] == "enumerate"]
    proven = [r for r in exact if r["status"] == "ok"]
    match = sum(r.get("matches_binary", False) for r in proven)
    certified = sum(r.get("binary_certified", False) for r in proven)
    calls = paired(rows, "search_oracle", "binary", "enumerate", "solver_calls")
    seam = paired(rows, "seam_oracle", "dp", "enumerate_gaps", "seam_segments")
    sifting = paired(rows, "sifting_oracle", "sift_zero", "enumerate_zero", "embedding_crossings")
    checks = [
        ("層数／左右通過辺（辞書式）", len(exact), len(proven), match, len(proven) - match),
        ("固定巻き数の順序・交差数", len(sifting), len(sifting),
         sum(a == b for _,a,b in sifting), sum(a != b for _,a,b in sifting)),
        ("固定埋め込みの切れ目 DP", len(seam), len(seam),
         sum(a == b for _,a,b in seam), sum(a != b for _,a,b in seam)),
    ]
    worst = max((a-b for _,a,b in sifting), default=None)
    return section("oracles", "6. 小規模入力での厳密照合", f'''
<p>階層数は 1 から n まで探索して、左右通過辺数・層数の辞書式最小値と照合した。順序探索は全ての巻き数を 0 に固定し、全ての層内順序の反転数を独立に計算した。切れ目は固定循環順序上の全切れ目について目的値を計算した。</p>
<p>階層数の全列挙が最適または実行不能と判定できた {len(proven)} 件のうち、二分探索側も判定が確定したのは {certified} 件。固定巻き数における sifting の最適交差数からの最大差は {fmt(worst)} だった。巻き数を動かせる本方式と厳密値を比べる試験では、別途その自由度を定式化する必要がある。</p>
''' + table("厳密解との一致", ("対象", "試行", "厳密比較可能", "一致", "不一致"), checks)
        + pair_table("二分探索 − 全列挙の求解回数", [stat_line("求解回数", calls)])
        + f'<p>二分探索単独の計測行は {len(binary)} 件。判定不能の候補は列挙側の厳密値に入れていない。</p>')


def scaling_section(root, rows):
    chart = profile_plot(root, rows)
    body = []
    for family in FAMILIES:
        for n in sorted({r["nodes"] for r in rows}):
            subset = [r for r in rows if r["family"] == family and r["nodes"] == n]
            if not subset:
                continue
            valid = [r for r in subset if r["status"] == "ok"]
            last = Counter(
                r.get("solver", [{}])[-1].get("name", "") for r in subset
                if r["status"] != "ok" and r.get("solver")
            )
            status = Counter(label(r["status"]) for r in subset if r["status"] != "ok")
            status_text = "、".join(f"{key} {count}" for key, count in status.items()) or "—"
            stage = "、".join(f"{key or '座標モデル'} {count}" for key, count in last.items()) or "—"
            body.append((f"{label(family)} · {n}", f"{len(valid)}/{len(subset)}",
                         sum(not bool(r.get("solver_limited")) for r in valid), status_text, stage,
                         median([r["layout_seconds"] for r in valid]) if valid else None,
                         median([r["peak_process_mib"] for r in valid]) if valid else None))
    phases = [("階層探索","find_minimum_configuration_seconds"), ("階層調整","balance_layers_seconds"),
              ("ダミー挿入","insert_dummy_nodes_seconds"), ("交差削減","reduce_crossings_seconds"),
              ("座標割当","assign_coordinates_seconds")]
    phase_rows = []
    for name, key in phases:
        available = [r for r in rows if r["status"] == "ok" and key in r]
        phase_rows.append((name, len(available), median([r[key] for r in available]) if available else None,
                           median([100*r[key]/r["layout_seconds"] for r in available]) if available else None))
    return section("scaling", "7. 規模、失敗、計算時間", '''
<p>頂点数と辺密度を振り、描画や幾何評価を除いた計算時間を測った。完走率と完走した例の時間を別々に読む。Gurobi 1 スレッドで実行したが、独立ケースは並行処理したため壁時計時間は環境と負荷の影響を含む。RSS には Python とライブラリのメモリが含まれる。</p>
''' + figure(chart, "大きさ別の完走率と、完走した例の中央値時間。グラフ族ごとの4系列。",
             "図 5。左は全試行を分母にした完走率。右は成功例の中央値。成功例のない所に時間は表示しない。")
        + table("段階別の所要時間（完走例）", ("工程", "件数", "中央値 (s)", "全体に対する中央値 (%)"), phase_rows)
        + table("グラフ族・頂点数別の完走と最終モデル", ("族 · 頂点数", "完了 / 試行",
                "ソルバー制限なしの完了", "非完走の状態", "最後に記録したモデル (非完走)",
                "時間中央値 (s)", "ピーク RSS 中央値 (MiB)"), body))


def drawing_section(root, rows):
    fixtures = [r for r in rows if r["experiment"] in ("drawing_geometry","crossing_counter")]
    test_rows = [(r["variant"], label(r["status"]), r.get("piece_count"), r.get("expected_piece_count"),
                  r.get("boundary_breaks"), r.get("arrow_count"), r.get("geometric_crossings"),
                  r.get("expected_crossings"), r.get("overlapping_edge_pairs")) for r in fixtures]
    media = '<div class="examples">'
    for name, caption in (("base","中央領域"), ("context","周辺タイルあり")):
        path = f"drawing/images/watts_strogatz-10-2-0-{name}.png"
        if (root/path).exists():
            media += figure(path, f"Watts–Strogatz 10頂点の{caption}の画像", caption)
    media += "</div>"
    return section("drawing", "8. 描画と周期境界の検査", '''
<p>固定座標の例で、境界を切った線分が周期的につながること、分割しても本来の辺長を保つこと、矢印が最後に一つだけあることを確認した。別の既知例で、交差カウンタが境界上の交差を一度だけ数え、共有端点と重なりを区別するかを検査した。</p>
''' + table("手計算の既知例との照合", ("例","状態","線分数","期待線分数","接続切れ","終端矢印",
                                            "幾何交差","期待交差","重なり辺対"), test_rows)
        + media
        + results_table("保存画像の代表値", rows, "render", ("base","context"), (
            ("figure_seconds","Figure 構築 (s)"), ("output_seconds","保存・合成 (s)"),
            ("image_width_px","幅 (px)"), ("image_height_px","高さ (px)"), ("image_bytes","サイズ (byte)"))))


def read_section(root):
    cases = read_csv(root/"readability"/"answer_key.csv")
    counts = Counter((r["size"],r["task"],r["wraps"]) for r in cases)
    media = '<div class="examples">'
    if cases:
        representative = next((r for r in cases if r["task"]=="distance" and r["wraps"]=="1"
                               and r["size"]=="20"),cases[0])
        for style, title in (("sugiyama","平面杉山法"),("torus_base","トーラス中央のみ"),
                             ("torus_context","トーラス＋周辺タイル")):
            path = f'readability/images/{representative["trial"]}-{style}.png'
            if (root/path).exists():
                media += figure(path,f"同じ読み取り課題を{title}で表示した画像",title)
    media += "</div>"
    return section("readability","9. 読み取り実験の準備",f'''
<p>{len(cases)} 問・{len(cases)*3} 画像を生成した。課題は矢印の向きと、有向最短経路の辺数。中心の配置・縮尺を固定し、周辺タイルの有無を比較できる。3 フォームに均等割付したとき、同じ項目が全体で 3 条件に回る。</p>
<p class="caution">参加者の回答はない。幾何交差が少ないことや、境界通過線分が減ることから、人の正答率や時間の効果を推定していない。</p>
<p><a href="readability/form_0.csv">出題フォーム 0</a> · <a href="readability/form_1.csv">フォーム 1</a> · <a href="readability/form_2.csv">フォーム 2</a> · <a href="readability/stimulus_audit.csv">刺激選定記録</a></p>
''' + table("生成した課題", ("課題", "頂点数", "境界を通る", "項目数"), [
        ("辺の向き" if task=="direction" else "最短経路の長さ", int(size), "あり" if wraps=="1" else "なし", count)
        for (size,task,wraps),count in sorted(counts.items())])
        + media)


def followup_section(root):
    records = read_csv(root/"followup"/"fixed_period.csv")
    data = []
    for row in records:
        if row["status"] != "ok":
            continue
        data.append({**row, "experiment": "fixed_period", **{
            k:float(row[k]) for k in ("period","bends","total_edge_length","geometric_crossings","gap_violations")
        }})
    comparisons = [(a, metric, paired(data,"fixed_period","bk_3x3",variant,metric))
                   for a,variant in (("既定 BK","default_bk"),("同一周期 BK","same_period_bk"))
                   for metric in ("period","bends","total_edge_length","geometric_crossings")]
    licenses = read_csv(root/"followup"/"license.csv")
    chart = difference_chart(root, "same_period", [
        (x, paired(data,"fixed_period","bk_3x3",v,"bends")) for x,v in
        (("3x3 minus default BK","default_bk"),("3x3 minus matched-period BK","same_period_bk"))
    ],"Change in bends per layout")
    guard_rows = [{**r, "experiment": "seam_guard", **{k:float(r[k]) for k in
                   ("seam_segments","y_seam_edges","geometric_crossings","total_edge_length")}}
                  for r in read_csv(root/"followup_guard"/"guarded_seams.csv") if r["status"]=="ok"]
    choices = (("DPのみとの比較（現行処理 − DPのみ）", "current_unwind_dp", "dp_only"),
               ("候補追加の効果（追加 − 現行処理）", "guarded_choice", "current_unwind_dp"),
               ("境界処理なしとの比較（追加 − 無処理）", "guarded_choice", "no_processing"))
    guard = pair_table("UNWINDなしのDP候補を残した場合", [
        stat_line(f"{name}／{measure}",paired(guard_rows,"seam_guard",a,b,key))
        for name,a,b in choices
        for measure,key in (("上下通過線分","seam_segments"), ("上下通過元辺","y_seam_edges"),
                            ("幾何交差","geometric_crossings"), ("総辺長","total_edge_length"))
    ])
    return section("followup","10. 結果を受けた追加実験",'''
<h3>10.1 3×3 BK の改善は周期の違いでも説明できるか</h3>
<p>通常の比較では 3×3 BK が曲がりを減らす一方で周期も変わる。そこで各族・頂点数・密度の seed 0 について、同じ層・順序・巻き数を使い、既定 BK の周期だけを 3×3 BK と同じ値に広げた。3×3 BK とこの対照の差は、共通の周期下で残る座標方式の差を示す。</p>
''' + figure(chart, "3×3 BKの曲がりの差を、既定周期のBKと同じ周期のBKに対して比較したグラフ。",
             "図 6。3×3 BK から比較先を引いた差。全て同一入力の対応差。")
        + pair_table("3×3 BK の周期を考慮した対応差",
                     [stat_line(f"3×3 − {label_text}／{key}",p) for label_text,key,p in comparisons])
        + '''
<h3>10.2 規模比較の失敗はローカル求解制限で説明できるか</h3>
<p>線形モデルと二次目的モデルで、制限とされる変数数・制約数の直下と直上を求解した。階層・座標の数値実験が記録したモデルエラーの解釈に使う。<a href="https://support.gurobi.com/hc/en-us/articles/360051597492-How-do-I-resolve-a-Model-too-large-for-size-limited-Gurobi-license-error">Gurobi の公式上限</a></p>
''' + table("ライセンス境界の実測", ("モデル","変数","線形制約","状態","エラー番号"), [
           (r["variant"], int(r["variables"]), int(r["constraints"]), label(r["status"]),
            r["solver_errno"] or "—") for r in licenses])
        + '''
<h3>10.3 UNWINDなしのDPを候補に残すと、悪化を避けられるか</h3>
<p>現行処理で上下通過線分が増える入力があったため、既定の候補に加え、UNWINDなしで切れ目だけを選んだ候補も残した。回転直後の同じ配置から出発し、通過線分数の少ない方を選んだ。候補選択の変更はこの追加実験に限った。10頂点の8例で実験内の現行条件が実際のパイプライン出力と一致することも確認した。</p>
''' + guard
        + '<p>追加実験の生データは <a href="followup/fixed_period.csv">周期統制</a>・<a href="followup/license.csv">制限確認</a>・<a href="followup_guard/guarded_seams.csv">境界候補の追加</a> に収録した。</p>')


def provenance_section(root, groups):
    inventory = []
    coverage = []
    for name in groups:
        folder = root/name
        settings_file = folder/"settings.json"
        if not settings_file.exists():
            continue
        settings = json.loads(settings_file.read_text())
        run_rows = read_rows(root,name)
        attempts = sum(1 for _ in (folder/"inputs.jsonl").open(encoding="utf-8")) if (folder/"inputs.jsonl").exists() else 0
        done = sum(r["status"]=="ok" for r in run_rows)
        coverage.append((name,attempts,len(run_rows),done,settings["solver_seconds"],
                          settings["case_seconds"],settings.get("jobs",1),
                          "完了" if (folder/"summary.csv").exists() else "途中記録"))
        links = [("設定","settings.json"),("入力","inputs.jsonl"),("ケース状態","cases.csv"),
                 ("生データ","rows.jsonl"),("表形式","results.csv"),
                 ("記述統計","summary.csv"),("対応比較","paired.csv"),("公開データ採否","benchmark_audit.csv")]
        inventory.append(f'<li><code>{escape(name)}</code> — ' + " · ".join(
            f'<a href="{name}/{path}">{text}</a>' for text,path in links
            if (folder/path).exists() and (folder/path).stat().st_size) + "</li>")
    return section("methods","実行条件と生データ",'''
<p>2026-11-20（日本時間）。既定の WLS 環境は Gurobi 環境生成で失敗したため、結果はローカルライセンスで取得した。Graphviz は 16.1.1、Python は 3.13.0、Gurobi は 13.0.0。大きな条件も試行できるよう、計画の生成サイズ・seed 数を今回の実行設定に絞った。</p>
<p>幾何交差は辺の中心線の横切り点を異なる元辺ごとに数え、重なりと接触を別にした。トーラスの基本領域上で重複を除外した。Graphviz は左から右へのポリライン指定と JSON 描画出力。放射の交差数は曲線のサンプリングに基づく。生の辺長や面積は描画方式の単位に依存する。</p>
<p>対応差は左側から右側を引いた値。対応数は両方の条件が完走し、同じ指標が得られた元グラフ数。平均差の bootstrap 区間はグラフ単位、2,000 反復。複数の比較を行ったため、区間は探索的な不確実性の表示として読む。制限付きの実行可能解を確認できるよう、試行表と生データにソルバー状態を残した。<a href="../../documents/experiment_plan.md">元の計画</a> · <a href="../../documents/sugiyama_experiment_literature_review.md">一次資料メモ</a></p>
''' + table("記録した実行条件", ("実行", "入力数", "測定行", "成功行", "求解上限 (s)", "worker上限 (s)",
                                      "並行ジョブ", "集計状態"),coverage)
        + f'<details open><summary>CSV・JSONL の一覧</summary><ul>{"".join(inventory)}</ul></details>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="Directory containing the experimental run directories")
    args = parser.parse_args()
    root = args.results
    groups = ("framework_timed","benchmark_framework","layering","subdivision","crossing",
              "coordinates","oracles_batched","scaling","drawing")
    runs = {name: read_rows(root,name) for name in groups}
    synthetic = runs["framework_timed"]
    overall = paired(synthetic,"framework","torus","sugiyama","geometric_crossings")
    seam = paired(runs["crossing"],"crossing_step","unwind_1_dp_1","unwind_0_dp_0","seam_segments")
    stimuli = len(read_csv(root/"readability"/"answer_key.csv"))
    sections = {
        "overview": "評価の要約", "framework": "全体比較", "layering": "階層割当", "subdivision": "ダミー挿入",
        "crossing": "交差・境界", "coordinates": "座標割当", "oracles": "厳密照合",
        "scaling": "規模", "drawing": "描画", "readability": "読解", "followup": "追加実験", "methods": "実行条件",
    }
    highlights = [
        (f"{len(overall)} 組","平面杉山とトーラスの交差を比較できた統制生成入力"),
        (f"{len(seam)} 組","UNWIND・DP の有無を比較できた入力"),
        (f"{stimuli} 問","読み取り実験の刺激"),
    ]
    cards = "".join(f'<div class="card"><strong>{amount}</strong>{caption}</div>' for amount,caption in highlights)
    evaluation_path = root/"evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8")) if evaluation_path.exists() else {}
    overview = section("overview","評価の要約",f'<div class="summary">{cards}</div>')
    nav = "".join(f'<li><a href="#{id_}">{title}</a></li>' for id_,title in sections.items())
    blocks = (overview, framework_section(root,synthetic,runs["benchmark_framework"]),
              layer_section(root,runs["layering"]), subdivision_section(runs["subdivision"]),
              crossing_section(root,runs["crossing"]), coordinate_section(root,runs["coordinates"]),
              oracle_section(runs["oracles_batched"]), scaling_section(root,runs["scaling"]),
              drawing_section(root,runs["drawing"]), read_section(root), followup_section(root),
              provenance_section(root,groups))
    body = ""
    for name, block in zip(sections, blocks, strict=True):
        notes = evaluation.get(name, ())
        explanation = "".join(f"<p>{escape(note)}</p>" for note in notes)
        if notes and name != "overview":
            explanation = "<h3>結果の評価</h3>" + explanation
        body += block.removesuffix("</section>") + explanation + "</section>"
    (root/"index.html").write_text(f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>トーラス階層グラフ描画の実験結果</title><style>{STYLE}</style></head>
<body><a class="skip" href="#main">本文へ移動</a>
<header><div class="date">2026.11.20</div><h1>トーラス階層グラフ描画の実験結果</h1>
<p>完成描画を既存方式と比較し、階層割当から境界表示まで、個々の処理が図にどう影響するかを測定した。</p></header>
<nav aria-label="目次"><ul>{nav}</ul></nav><main id="main">{body}</main>
<footer><p>ケースごとの結果と実行設定は「実行条件と生データ」から確認できる。</p></footer></body></html>
''',encoding="utf-8")


if __name__ == "__main__":
    main()
