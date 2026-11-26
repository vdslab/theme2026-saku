"""Regenerate tables, trajectory plots, and matched-scale drawings from saved runs."""

import argparse
from collections import Counter
import csv
from math import hypot
from pathlib import Path
from statistics import mean, median

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection

from evaluate_global_block_order import (
    FAMILIES, METHODS, MODES, OUTPUT, SIZES, original, read, subdivided, unpack,
)
from torus_layout.models import CoordinateResult
from torus_study.geometry import torus_routes
from torus_study.stages import chains_for

LABELS = {"forward": "Forward every round", "alternating": "Alternating forward / reverse"}
COLORS = {"forward": "#164e85", "alternating": "#bc521e"}
FAMILY_NAMES = dict(random="ランダム有向", scc_chain="SCC連結", watts_strogatz="WS")
MODE_NAMES = dict(fixed="固定5周", early="早期終了あり・上限5周")
QUALITY = ("geometric_crossings", "bends", "either_seam_edges")
PX_PER_LAYER = 64
DPI = 128


def csv_file(path, rows):
    if rows:
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def matched(cases, mode):
    for case in cases:
        methods = {row["method"]: row for row in case["trials"]
                   if row["mode"] == mode and row["status"] == "ok"}
        if all(method in methods for method in METHODS):
            yield case, *(methods[method] for method in METHODS)


def difference(values):
    return (sum(x < 0 for x in values), values.count(0), sum(x > 0 for x in values),
            median(values) if values else None)


def summarize(output, cases, mode):
    groups = [("全体", "全系列", cases)]
    groups.extend((n, FAMILY_NAMES[family], [c for c in cases if c["n"] == n and c["family"] == family])
                  for n in SIZES for family in FAMILIES)
    summaries = []
    for n, family, group in groups:
        pairs = list(matched(group, mode))
        delta = [b["crossings"] - a["crossings"] for _, a, b in pairs]
        win, tie, loss, med = difference(delta)
        quality = [(a["drawing"], b["drawing"]) for _, a, b in pairs
                   if a["drawing"]["status"] == b["drawing"]["status"] == "ok"]
        row = dict(n=n, family=family, inputs=len(group), completed=sum(c["done"] for c in group),
                   pairs=len(pairs), improved=win, tied=tie, worsened=loss, median_delta=med,
                   forward_seconds=median([a["seconds"] for _, a, _ in pairs]) if pairs else None,
                   alternating_seconds=median([b["seconds"] for _, _, b in pairs]) if pairs else None,
                   median_seconds_delta=median([b["seconds"] - a["seconds"] for _, a, b in pairs])
                   if pairs else None,
                   median_candidate_delta=median([b["candidates"] - a["candidates"] for _, a, b in pairs])
                   if pairs else None,
                   forward_median_rounds=median([a["rounds"] for _, a, _ in pairs]) if pairs else None,
                   alternating_median_rounds=median([b["rounds"] for _, _, b in pairs]) if pairs else None,
                   geometry_pairs=len(quality))
        for metric in QUALITY:
            values = [b[metric] - a[metric] for a, b in quality]
            for suffix, value in zip(("improved", "tied", "worsened", "median_delta"), difference(values)):
                row[f"{metric}_{suffix}"] = value
        summaries.append(row)
    csv_file(output / f"summary_{mode}.csv", summaries)
    return summaries


def series(row):
    return [entry["crossings"] for entry in row["trace"]]


def plot_trajectories(output, pairs, mode, examples):
    if not pairs:
        return
    fig, axes = plt.subplots(1, 1 + len(examples), figsize=(5 * (1 + len(examples)), 4.4),
                             squeeze=False, layout="constrained")
    axes = axes[0]
    means = {}
    for i, method in enumerate(METHODS, 1):
        curves = [series(pair[i]) for pair in pairs]
        averages = [mean(curve[min(index, len(curve) - 1)] for curve in curves)
                    for index in range(6)]
        means[method] = averages
        axes[0].plot(range(6), averages, "o-", color=COLORS[method], label=LABELS[method],
                     markersize=4, alpha=.85)
        for ax, pair in zip(axes[1:], examples):
            curve = series(pair[i])
            ax.plot(range(len(curve)), curve, "o-", color=COLORS[method], markersize=4, alpha=.85)
    axes[0].set_title(f"Paired mean · {len(pairs)} inputs")
    axes[0].legend(frameon=False, fontsize=9)
    for ax, (case, a, b) in zip(axes[1:], examples):
        ax.set_title(f"{case['id']}\nFinal difference {b['crossings'] - a['crossings']:+d}")
    for ax in axes:
        ax.set(xlabel="Round (0 = initial block embedding)", ylabel="Embedding crossings",
               xticks=range(6))
        ax.grid(alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    delta = axes[0].inset_axes((.54, .30, .4, .34))
    delta.plot(range(6), [b - a for a, b in zip(*(means[method] for method in METHODS))],
               ".-", color="#525166")
    delta.axhline(0, color="#aab1b8", linewidth=.7)
    delta.set(title="Mean difference (alt − fwd)", xticks=range(6))
    delta.title.set_fontsize(8)
    delta.tick_params(labelsize=7)
    delta.spines[["top", "right"]].set_visible(False)
    mode_title = ("Five fixed rounds" if mode == "fixed"
                  else "Early stop · mean carries forward the final observed value")
    fig.suptitle(mode_title, fontweight="bold")
    fig.savefig(output / f"trajectory_{mode}.png", dpi=160, facecolor="white")
    plt.close(fig)


def drawing(output, case, first, second, mode):
    graph = original(case)
    sub = subdivided(graph, read(output / "prepared" / f"{case['id']}.json"))
    chains = chains_for(graph, sub)
    panels = []
    for trial in (first, second):
        saved = trial["drawing"]
        crossing = unpack(saved["crossing"])
        coords = CoordinateResult(dict(saved["positions"]), saved["period"])
        routes, bounds = torus_routes(chains, sub, crossing, coords)
        panels.append((saved, coords, routes, bounds))
    layers = len(sub.layers)
    panel_width = layers * PX_PER_LAYER
    left, gap, bottom, top = 26, 38, 36, 109
    height = round(max(item[3][3] for item in panels) * PX_PER_LAYER)
    width = max(640, 2 * left + gap + 2 * panel_width)
    left = (width - 2 * panel_width - gap) // 2
    total_height = bottom + top + height
    fig = plt.figure(figsize=(width / DPI, total_height / DPI), dpi=DPI)
    caption = "Fixed 5 rounds" if mode == "fixed" else "Early stop, max 5 rounds"
    fig.text(.5, 1 - 17 / total_height, f"{case['id']}  ·  {caption}", ha="center", va="top",
             fontsize=11, fontweight="bold")
    fig.text(.5, 14 / total_height, "Gray: ordinary   ·   Orange: horizontal cut   ·   Blue: vertical cut",
             ha="center", va="center", fontsize=7, color="#57616b")
    for i, (method, (saved, coords, routes, bounds)) in enumerate(zip(METHODS, panels)):
        x, y, w, h = bounds
        x_start = left + i * (panel_width + gap)
        panel_height = h * PX_PER_LAYER
        y_start = bottom + (height - panel_height) / 2
        ax = fig.add_axes((x_start / width, y_start / total_height,
                           panel_width / width, panel_height / total_height))
        ax.set(xlim=(x, x + w), ylim=(y, y + h), xticks=[], yticks=[])
        ax.set_facecolor("#fbfcfd")
        ax.vlines(range(layers), y, y + h, color="#dfe4e9", linewidth=.35)
        colors = {"ordinary": "#44515e", "horizontal": "#c56a28", "vertical": "#1765a5"}
        def edge_color(route):
            return "vertical" if route.y_wraps else "horizontal" if route.x_wraps else "ordinary"

        for name, color in colors.items():
            pieces = [segment for route in routes for segment in route.pieces
                      if name == edge_color(route)]
            ax.add_collection(LineCollection(pieces, colors=color, linewidths=.62, alpha=.74))
            arrows = []
            for route in routes:
                if not route.pieces or edge_color(route) != name:
                    continue
                start, end = route.pieces[-1]
                dx, dy = end[0] - start[0], end[1] - start[1]
                length = hypot(dx, dy)
                if length < .15:
                    continue
                ux, uy = dx / length, dy / length
                tip = end[0] - .055 * ux, end[1] - .055 * uy
                base = tip[0] - .07 * ux, tip[1] - .07 * uy
                arrows.append([(base[0] - .031 * uy, base[1] + .031 * ux), tip,
                               (base[0] + .031 * uy, base[1] - .031 * ux)])
            ax.add_collection(LineCollection(arrows, colors=color, linewidths=.62, alpha=.84))
        xs, ys = zip(*(coords.positions[node] for node in graph.nodes))
        ax.scatter(xs, ys, s=11, c="#22394d", edgecolors="white", linewidth=.38, zorder=4)
        if len(graph.nodes) <= 40:
            for node, nx, ny in zip(graph.nodes, xs, ys):
                ax.annotate(str(node), (nx, ny), xytext=(3, 2), textcoords="offset points",
                            fontsize=5, color="#152635", zorder=5)
        for spine in ax.spines.values():
            spine.set(color="#aeb8c1", linewidth=.6)
        center = (x_start + panel_width / 2) / width
        fig.text(center, 1 - 48 / total_height, LABELS[method], ha="center",
                 fontsize=9, color=COLORS[method], fontweight="bold")
        text = (f"Geom. crossings {saved['geometric_crossings']}  ·  Bends {saved['bends']}\n"
                f"Original edges through either seam {saved['either_seam_edges']}")
        fig.text(center, 1 - 60 / total_height, text, ha="center", va="top", fontsize=8)
        pixel_step = ax.transData.transform((1, 0))[0] - ax.transData.transform((0, 0))[0]
        assert abs(pixel_step - PX_PER_LAYER) < 1e-8
    path = output / "drawings" / f"{mode}_{case['id']}.png"
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


def show(value, digits=None):
    if value is None:
        return "—"
    return f"{value:.{digits}f}" if digits is not None else f"{value:g}"


def markdown_table(rows):
    lines = ["| 頂点数 | 系列 | 試行 | 比較ペア | 減／同／増 | Δ交差 中央値 | 秒 順／交互 | Δ秒 中央値 | Δ候補 中央値 | 図ペア |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        lines.append(f"| {r['n']} | {r['family']} | {r['inputs']} | {r['pairs']} | "
                     f"{r['improved']}／{r['tied']}／{r['worsened']} | {show(r['median_delta'])} | "
                     f"{show(r['forward_seconds'], 3)}／{show(r['alternating_seconds'], 3)} | "
                     f"{show(r['median_seconds_delta'], 3)} | {show(r['median_candidate_delta'])} | "
                     f"{r['geometry_pairs']} |")
    return lines


def trajectory_rows(pairs, mode):
    rows = []
    for case, a, b in pairs:
        for method, trial in zip(METHODS, (a, b)):
            rows.extend(dict(case=case["id"], mode=mode, method=method, round=t["round"],
                             crossings=t["crossings"], visits=t.get("visits", 0),
                             candidates=t.get("candidates", 0)) for t in trial["trace"])
    return rows


def measurements(cases):
    for case in cases:
        for mode in MODES:
            for method in METHODS:
                trial = next((t for t in case["trials"]
                              if t["mode"] == mode and t["method"] == method), {})
                drawing = trial.get("drawing", {})
                yield dict(case=case["id"], n=case["n"], family=case["family"], mode=mode,
                           method=method, preparation=case["prep_status"], sifting=trial.get("status"),
                           seconds=trial.get("seconds"), rounds=trial.get("rounds"), visits=trial.get("visits"),
                           candidates=trial.get("candidates"), crossings=trial.get("crossings"),
                           drawing=drawing.get("status"), boundary_method=drawing.get("method"),
                           fallback=drawing.get("fallback"), **{k: drawing.get(k) for k in QUALITY})


def report(output):
    cases = read(output / "inputs.json")
    for case in cases:
        path = output / "cases" / f"{case['id']}.json"
        case.update(read(path) if path.exists() else dict(prep_status="pending", trials=[]))
        case["done"] = path.exists()
    settings = read(output / "settings.json")
    (output / "drawings").mkdir(exist_ok=True)
    statuses = Counter(c["prep_status"] for c in cases)
    sources = Counter(c["source"] for c in cases)
    preps = [read(output / "prepared" / f"{c['id']}.json") for c in cases if c["prep_status"] == "ok"]
    limited = sum(any(m["status"] == 9 for m in prep["solver"]) for prep in preps)
    retries = Counter(c["layer_retry_seconds"] for c in cases if c.get("layer_retry_seconds"))
    lines = ["# Global sifting のブロック訪問順比較", "",
             f"入力は{len(cases)}件。階層割当の結果は " +
             "、".join(f"`{s}` {n}件" for s, n in sorted(statuses.items())) + "。",
             f"有効な階層割当のうち{limited}件で、少なくとも一つのGurobiモデルが時間上限に到達した。"
             "現行の階層探索が採用し、割当の制約検証を通過した結果を共通入力として使用した。", "",
             "| 頂点数 | 割当成功 | ライセンス上限 | 割当時間切れ | その他の割当失敗 | 未実行 |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for n in SIZES:
        by_size = Counter(c["prep_status"] for c in cases if c["n"] == n)
        known = ("ok", "license_limit", "layer_timeout", "pending")
        other = sum(count for status, count in by_size.items() if status not in known)
        lines.append(f"| {n} | {by_size['ok']} | {by_size['license_limit']} | {by_size['layer_timeout']} | "
                     f"{other} | {by_size['pending']} |")
    lines.extend(["",
             "Δは入力ごとの「交互−順方向」。秒の列は、両条件が完走したペアで求めた各条件の中央値。",
             "試行の分母には、階層割当の失敗とsifting時間切れを含む。図の指標は両条件で得られたペアから集計。", ""])
    all_trajectories, all_drawings, divergence_rows, drawing_errors = [], [], [], []
    for mode in MODES:
        rows = summarize(output, cases, mode)
        pairs = list(matched(cases, mode))
        lines.extend([f"## {MODE_NAMES[mode]}", "", *markdown_table(rows), ""])
        mode_trials = [t for c in cases for t in c["trials"] if t["mode"] == mode]
        sift_status = Counter(t["status"] for t in mode_trials)
        draw_status = Counter(t["drawing"]["status"] for t in mode_trials if "drawing" in t)
        fallbacks = sum(t.get("drawing", {}).get("fallback", False) for t in mode_trials)
        lines.append("条件別実行のsifting結果は " +
                     "、".join(f"`{status}` {count}件" for status, count in sorted(sift_status.items())) +
                     "。描画工程の結果は " +
                     "、".join(f"`{status}` {count}件" for status, count in sorted(draw_status.items())) +
                     f"。従来の境界処理へのフォールバック試行は{fallbacks}件。")
        if not pairs:
            lines.append("")
            continue

        first_divergences = Counter()
        for case, a, b in pairs:
            curves = series(a), series(b)
            first = next((i for i, values in enumerate(zip(*curves)) if values[0] != values[1]), None)
            first_divergences[first] += 1
            divergence_rows.append(dict(case=case["id"], mode=mode, first_crossing_divergence=first,
                                        final_embedding_equal=a["final"] == b["final"],
                                        final_delta=b["crossings"] - a["crossings"]))
        assert not (first_divergences[0] or first_divergences[1])
        first_diff = "、".join(f"{i}周目 {first_divergences[i]}件"
                              for i in range(2, 6) if first_divergences[i])
        visits_equal = sum(a["visits"] == b["visits"] for _, a, b in pairs)
        round_histograms = [Counter(p[i]["rounds"] for p in pairs) for i in (1, 2)]
        lines.extend(["", f"訪問回数が同じペアは{visits_equal}/{len(pairs)}件。"
                      f"両条件で実際に観測した周で交差数が初めて異なった内訳は{first_diff or '該当なし'}。"
                      f"共通の観測範囲で一致したのは{first_divergences[None]}件。"])
        if mode == "early":
            hist = ["、".join(f"{k}周 {v}件" for k, v in sorted(h.items())) for h in round_histograms]
            lines.append(f"完走ペアでの終了周は順方向が{hist[0]}、交互が{hist[1]}。")
        cand = [b["candidates"] - a["candidates"] for _, a, b in pairs]
        counts = difference(cand)
        speed = [b["seconds"] / a["seconds"] for _, a, b in pairs]
        deltas = [b["crossings"] - a["crossings"] for _, a, b in pairs]
        nonzero = [abs(value) for value in deltas if value]
        if nonzero:
            lines.append(f"最終交差数の対応差は{min(deltas):+d}〜{max(deltas):+d}。"
                         f"差があった{len(nonzero)}件での絶対差の中央値は{median(nonzero):g}交差。")
        lines.extend([
            f"採点候補数は交互で減少{counts[0]}件、同数{counts[1]}件、増加{counts[2]}件。"
            f"対応差は{min(cand):+d}〜{max(cand):+d}候補、時間比（交互／順）の中央値は{median(speed):.3f}倍。",
            "",
            "| 完成図の指標 | 比較ペア | 減／同／増 | Δ中央値 |",
            "| --- | ---: | ---: | ---: |",
        ])
        for metric, label in zip(QUALITY, ("幾何交差数", "折れ数", "境界を通る元辺数")):
            row = rows[0]
            result = "／".join(str(row[f"{metric}_{key}"]) for key in ("improved", "tied", "worsened"))
            lines.append(f"| {label} | {row['geometry_pairs']} | {result} | {show(row[f'{metric}_median_delta'])} |")
        both_differ = Counter()
        for _, a, b in pairs:
            if a["drawing"]["status"] == b["drawing"]["status"] == "ok":
                embedding = b["crossings"] - a["crossings"]
                geometric = b["drawing"]["geometric_crossings"] - a["drawing"]["geometric_crossings"]
                if embedding:
                    both_differ["same_sign" if embedding * geometric > 0 else
                                "opposite" if geometric else "zero"] += 1
                elif geometric:
                    both_differ["geometry_only"] += 1
        same_crossings_different_state = sum(
            a["crossings"] == b["crossings"] and a["final"] != b["final"] for _, a, b in pairs
        )
        by_size = []
        for n in SIZES:
            values = [b["crossings"] - a["crossings"] for c, a, b in pairs if c["n"] == n]
            if values:
                by_size.append(f"{n}頂点 {sum(bool(d) for d in values)}/{len(values)}件")
        by_family = []
        for family, label in FAMILY_NAMES.items():
            values = [b["crossings"] - a["crossings"] for c, a, b in pairs if c["family"] == family]
            if values:
                win, tie, loss, _ = difference(values)
                by_family.append(f"{label} {win}／{tie}／{loss}")
        lines.extend(["",
                      f"両条件の完成図があり、埋め込み交差に差があったペアでは、幾何交差も同方向に"
                      f"変わったのが{both_differ['same_sign']}件、幾何交差が同数だったのが"
                      f"{both_differ['zero']}件、逆方向だったのが{both_differ['opposite']}件。"
                      f"埋め込み交差が同数で幾何交差が異なったのは{both_differ['geometry_only']}件。",
                      f"最終の埋め込み交差が同数でも層順か巻き数が異なったのは"
                      f"{same_crossings_different_state}件。",
                      f"サイズ別に最終交差数が異なったのは{'、'.join(by_size)}。"
                      f"系列別の交差減／同／増は{'、'.join(by_family)}。", ""])
        ranked = sorted(pairs, key=lambda p: p[2]["crossings"] - p[1]["crossings"])
        examples = []
        if ranked[0][2]["crossings"] < ranked[0][1]["crossings"]:
            examples.append(ranked[0])
        if ranked[-1][2]["crossings"] > ranked[-1][1]["crossings"]:
            examples.append(ranked[-1])
        plot_trajectories(output, pairs, mode, examples)
        lines.extend([f"![{MODE_NAMES[mode]}の交差推移](trajectory_{mode}.png)", ""])
        if mode == "early":
            lines.extend(["全体平均では早期終了後の周に最終値を延長した。個別例は実際に観測した周まで表示。", ""])
        example_keys = {case["id"] for case, _, _ in examples}
        for case, a, b in pairs:
            if a["drawing"]["status"] != "ok" or b["drawing"]["status"] != "ok":
                continue
            different = any(a["drawing"][k] != b["drawing"][k] for k in QUALITY)
            if different or a["final"] != b["final"]:
                try:
                    path = drawing(output, case, a, b, mode)
                except (ValueError, RuntimeError, OSError) as error:
                    drawing_errors.append(dict(mode=mode, case=case["id"], error=str(error)))
                    continue
                all_drawings.append(dict(mode=mode, case=case["id"], image=str(path.relative_to(output))))
                if case["id"] in example_keys:
                    lines.extend([f"![{case['id']} の完成図]({path.relative_to(output)})", ""])
        all_trajectories.extend(trajectory_rows(pairs, mode))

    csv_file(output / "measurements.csv", list(measurements(cases)))
    csv_file(output / "paired_trajectories.csv", all_trajectories)
    csv_file(output / "divergence.csv", divergence_rows)
    csv_file(output / "drawings.csv", all_drawings)
    csv_file(output / "drawing_errors.csv", drawing_errors)
    mode_matches = []
    for case in cases:
        trials = {(row["mode"], row["method"]): row for row in case["trials"] if row["status"] == "ok"}
        for method in METHODS:
            if all((mode, method) in trials for mode in MODES):
                mode_matches.append(trials["fixed", method]["final"] == trials["early", method]["final"])
    if mode_matches:
        lines.extend([
            "## 固定周数と早期終了", "",
            f"同じ入力・訪問順で両モードが完走した{len(mode_matches)}条件のうち、"
            f"最終層順・巻き数が一致したのは{sum(mode_matches)}条件。"
            "採用移動が一度もない周では、すべてのブロックが同じ状態で採点される。"
            "その状態からさらに周を重ねても、どちらの訪問方向でも採用できる移動は発生しない。", "",
        ])
    lines.extend([
        "## 設定と再現", "",
        f"- 完成図の比較画像を{len(all_drawings)}枚保存。画像保存の失敗は{len(drawing_errors)}件。"
        "保存に失敗した場合は `drawing_errors.csv` に記録。",
        "- 20・40・60・80・100頂点、各サイズでランダム有向5件、SCC連結5件、WS 10件。"
        "辺は2n本。ランダム有向・SCC連結は既存トーラス研究の生成器。WSは近傍4、再配線0.8、"
        "seed 0〜9、連結条件付きの前回WS実験の設定。",
        "- 入力の来歴は " + "、".join(f"`{s}` {n}件" for s, n in sources.items()) + "。",
        f"- 階層割当は既存の探索とdiff_square。ローカルライセンス、モデルごと"
        f"{settings['solver_seconds_per_model']:g}秒、1スレッド、solver seed 0。"
        f" siftingは1条件あたり{settings['sifting_seconds_per_run']:g}秒を上限とした。",
        *(["- 階層割当が時間切れで解を返さなかった入力のみ、" +
           "、".join(f"モデルごと{seconds:g}秒で{count}件" for seconds, count in sorted(retries.items())) +
           "を再試行した。初回のログを `prepared/` の `previous_attempt` に保存した。"] if retries else []),
        "- 初期値は既定のbarycenter順を共有ブロック順へ射影した直後で、全巻き数は0。"
        "各周の開始時に訪問順をスナップショット化し、確定した移動を即時反映する。",
        "- 本計測前に20頂点で、第1周の訪問順、層順、巻き数の一致と、"
        "早期終了ありの順方向が変更前の実装と同じ最終状態になることを確認した。",
        "- 実行順を入力ごとに入れ替え、siftingカーネルを直列で1回計時。"
        "計数と各周の交差数は同じ入力での別実行で測り、全完走試行で最終状態の一致を確認。"
        "スキップ後に採点へ進んだ挿入位置を各1候補と数えた。時間切れ試行では上限到達時間を記録した。",
        "- 一部入力の計数は複数プロセスで再実行し、全て完了してから次の入力の計時に進んだ。"
        "再実行のプロセス数は各ケースの `trace_workers` に保存した（省略時は1）。",
        "- 完成図は既定の同時境界最適化と分割なしBrandes–Köpf座標。"
        "既定パイプラインと同条件で従来の境界処理へのフォールバックを適用。"
        "境界を通る元辺数は左右・上下の和集合。図は左が順方向、右が交互で、横1層64 px、上下は余白調整。",
        "",
        "保存先は `inputs.json`（入力）、`settings.json`（条件）、`pilot.json`（予備検証）、"
        "`prepared/`（割当、境界フラグ、分割、初期順・巻き数、solverログ）、"
        "`cases/`（両条件の周ごとの訪問順・交差数・候補数および最終層順・巻き数、完成図用座標）、"
        "`measurements.csv`、`summary_fixed.csv`、`summary_early.csv`、`paired_trajectories.csv`、"
        "`divergence.csv`、`drawings.csv`（完成図の索引）。", "",
        "```sh",
        "export PYTHONHASHSEED=0 PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-block-mpl",
        "./theme2026-saku/bin/python experiments/evaluate_global_block_order.py --trace-workers 4",
        *(["./theme2026-saku/bin/python experiments/evaluate_global_block_order.py "
           f"--trace-workers 4 --retry-layer-seconds {seconds:g}" for seconds in sorted(retries)]),
        "./theme2026-saku/bin/python experiments/report_global_block_order.py",
        "```", "",
        "計測コマンドは既存のケース結果から再開する。時間も再計測する場合は別の `--output` を指定。"
        "同じ初期配置を使うには、新しい出力先へ保存済みの `inputs.json` と `prepared/` をコピーしてから実行する。"
        "レポートコマンドは保存済みデータから表と図を再生成する。",
        "",
        "変更前の実装との予備比較を再実行する場合は、新しい出力先を指定し、計測コマンドに "
        "`--pilot-only --baseline output/global_block_order_20261126/baseline_global_sifting.py` を加える。",
    ])
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    report(parser.parse_args().output)
