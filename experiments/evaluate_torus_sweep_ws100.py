"""WS complex-network comparison, n=10..100, with English presentation figures.

Run with the project interpreter. --resume reuses completed cases and embeddings;
--summarize-only regenerates figures and the report without solving or sifting.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

import evaluate_torus_sweep_direction as base
from layer_assignment.torus_binary_search import find_minimum_torus_configuration

OUTPUT = base.OUTPUT / "ws100"
NODE_COUNTS = tuple(range(10, 101, 10))
SEEDS = tuple(range(10))
NEIGHBORS = 4
REWIRING = 0.8
LABELS = {
    "alternating": "往復",
    "cyclic": "循環（各ペア1回）",
    "current_cyclic": "循環（各ペア5回・現行）",
}
PLOT_LABELS = {
    "alternating": "Alternating",
    "cyclic": "Cyclic (1 pass per pair)",
    "current_cyclic": "Cyclic (5 passes per pair; current)",
}
COLORS = {"alternating": "#64748b", "cyclic": "#2563eb", "current_cyclic": "#d97706"}


def parameters(quick=False):
    sizes = (10, 100) if quick else NODE_COUNTS
    seeds = (0,) if quick else SEEDS
    return [dict(nodes=n, neighbors=NEIGHBORS, rewiring_probability=REWIRING, seed=s)
            for n in sizes for s in seeds]


def case_id(parameter):
    return f"n{parameter['nodes']}_k{parameter['neighbors']}_p{parameter['rewiring_probability']}_s{parameter['seed']}"


def prepare(parameter):
    started = time.perf_counter()
    vertices, edges = base.generate_watts_strogatz_graph(
        parameter["nodes"], k=parameter["neighbors"], p=parameter["rewiring_probability"],
        seed=parameter["seed"], ensure_connected=True,
    )
    edges = sorted(set(edges))
    layer_count, torus_count, _ = find_minimum_torus_configuration(vertices, edges)
    if layer_count is None or torus_count is None:
        raise RuntimeError(f"Layer-count search failed for {case_id(parameter)}")
    embedding = base.prepare_embedding({**parameter, "edges": len(edges),
                                        "exact_layer_count": layer_count,
                                        "exact_torus_count": torus_count})
    embedding["preparation_seconds"] = time.perf_counter() - started
    return embedding


def evaluate_method(arguments):
    return base.evaluate(*arguments)


def evaluate_case(embedding, index, rounds, executor=None, workers=1):
    order = dict(embedding["order"])
    psi = {tuple(edge): value for edge, value in embedding["psi"]}
    edges = [tuple(edge) for edge in embedding["edges"]]
    layers = embedding["layers"]
    initial = base.radial._count_all_crossings(order, psi, layers, edges)
    rows, traces = [], []
    execution = base.METHODS[index % 3:] + base.METHODS[:index % 3]
    inputs = [(order, psi, layers, edges, set(embedding["dummy_nodes"]),
               base.schedule(layers, method, rounds)) for method in execution]
    results = list(executor.map(evaluate_method, inputs)) if executor else list(map(evaluate_method, inputs))
    for method, (result, trace) in zip(execution, results):
        print(f"  {method}: final={result['final_crossings']} best={result['guarded_crossings']} ({result['trajectory_seconds']:.2f}s)", flush=True)
        row = {key: embedding[key] for key in ("case_id", "nodes", "neighbors", "rewiring_probability", "seed", "layer_count", "torus_count")}
        row.update(method=method, rounds=rounds, original_edges=len(embedding["original_edges"]),
                   proper_edges=len(edges), dummy_nodes=len(embedding["dummy_nodes"]),
                   initial_crossings=initial, execution_workers=workers, **result)
        rows.append(row)
        traces.extend(dict(case_id=embedding["case_id"], method=method, step=t["step"],
                           fixed_layer=t.get("fixed_layer", ""), free_layer=t.get("free_layer", ""),
                           crossings=t["crossings"], best_crossings=t["best_crossings"],
                           elapsed_seconds=t["elapsed_seconds"]) for t in trace)
    return rows, traces


def summarize(rows):
    summaries = []
    for metric in ("final_crossings", "guarded_crossings"):
        summaries.extend(base.summarize(rows, metric, "all"))
        for n in sorted({r["nodes"] for r in rows}):
            summaries.extend(base.summarize([r for r in rows if r["nodes"] == n], metric, f"n={n}"))
    return summaries


def plotting():
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/torus-sweep-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams.update({"font.size": 11, "axes.unicode_minus": False, "svg.fonttype": "path"})
    return plt


def save_figure(fig, output, name):
    for ext in ("png", "svg"):
        fig.savefig(output / f"{name}.{ext}", dpi=180, facecolor="white")


def plot(rows, summaries, traces, output):
    plt = plotting()
    ns = sorted({r["nodes"] for r in rows})
    cases = len(rows) // 3
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), gridspec_kw={"width_ratios": [1, 1.2]})
    for row_index, (metric, title) in enumerate((("final_crossings", "Final state"),
                                               ("guarded_crossings", "Best state retained"))):
        left, right = axes[row_index]
        lookup = {(r["scope"], r["method"]): r for r in summaries if r["metric"] == metric}
        for method in base.METHODS:
            vals = [lookup[(f"n={n}", method)]["mean_crossings"] for n in ns]
            left.plot(ns, vals, "o-", color=COLORS[method], label=PLOT_LABELS[method], linewidth=2, markersize=5)
        left.set_title(f"{title}: crossings", loc="left", fontweight="bold")
        left.set_ylabel("Mean crossings (lower is better)")
        left.set_ylim(bottom=0, top=max(1, left.get_ylim()[1] * 1.12))
        for method, offset in (("cyclic", -1.8), ("current_cyclic", 1.8)):
            reductions = [lookup[(f"n={n}", method)]["pooled_reduction_percent"] if lookup[(f"n={n}", "alternating")]["total_crossings"] else float("nan") for n in ns]
            right.bar([n + offset for n in ns], reductions, width=3.4, color=COLORS[method], label=PLOT_LABELS[method], alpha=.9)
        right.axhline(0, color="#475569", linewidth=1)
        right.set_title(f"{title}: reduction vs. alternating", loc="left", fontweight="bold")
        right.set_ylabel("Pooled crossing reduction (%)")
        right.text(.02, .97, "+: fewer crossings / −: more crossings", transform=right.transAxes, va="top", fontsize=9)
        # Extra room keeps the sign explanation separate from the bars.
        low, high = right.get_ylim()
        right.set_ylim(low - .03 * (high - low), high + .14 * (high - low))
        for ax in (left, right):
            ax.set_xlabel("Original nodes")
            ax.set_xticks(ns)
            ax.grid(axis="y", alpha=.18)
            ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Torus crossing reduction: alternating vs. cyclic sweeps", fontsize=20, fontweight="bold", y=.98)
    fig.text(.5, .934, f"Watts–Strogatz (k=4, p=0.8) | {cases} paired graphs | Same initial state and local-pass budget", ha="center", fontsize=11, color="#475569")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="upper center", bbox_to_anchor=(.5, .92), frameon=False)
    fig.text(.5, .018, "Blue: cycle with 1 pass per pair | Orange: 5 consecutive passes per pair (current)", ha="center", fontsize=11)
    fig.subplots_adjust(top=.84, bottom=.10, hspace=.38, wspace=.27)
    save_figure(fig, output, "sweep_comparison")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for method in base.METHODS:
        curves = {}
        for t in traces:
            if t["method"] == method:
                curves.setdefault(t["case_id"], []).append(t)
        progress = range(101)
        means = [statistics.mean(curve[min(len(curve) - 1, int(p / 100 * (len(curve) - 1)))]["best_crossings"] for curve in curves.values()) for p in progress]
        ax.plot(progress, means, color=COLORS[method], label=PLOT_LABELS[method], linewidth=2)
    ax.set(title="Best-so-far crossings during sifting\n(before rotation postprocessing)", xlabel="Local-pass budget consumed (%)", ylabel="Mean best-so-far crossings (lower is better)")
    ax.legend(frameon=False)
    ax.grid(alpha=.18)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save_figure(fig, output, "sweep_trajectory")
    plt.close(fig)


def write_report(rows, summaries, output):
    ns = sorted({r["nodes"] for r in rows})
    seeds = sorted({r["seed"] for r in rows})
    cases = len(rows) // 3
    overall = {(r["metric"], r["method"]): r for r in summaries if r["scope"] == "all"}
    lines = ["# 複雑ネットワークでのトーラス交差削減：最大100頂点", "",
             f"頂点数{', '.join(map(str, ns))}、各サイズ{len(seeds)} seed（{', '.join(map(str, seeds))}）、計**{cases}グラフ**。",
             "リポジトリの `generate_watts_strogatz_graph` を使用。メインコードのWS生成例と同じ近傍数4・再配線確率0.8。連結な無向WS構造を生成し、円環上で短い時計回り方向へ有向化する。辺数は2n。", "",
             "## まず見る結果", "",
             "|配置の採用方法|往復の合計交差数|循環・各ペア1回|往復比|循環・各ペア5回（現行）|往復比|", "|---|---:|---:|---:|---:|---:|"]
    for metric, label in (("final_crossings", "最後の配置"), ("guarded_crossings", "途中の最良配置を保存")):
        a, b, c = [overall[(metric, m)] for m in base.METHODS]
        lines.append(f"|{label}|{a['total_crossings']:,}|{b['total_crossings']:,}|{b['pooled_reduction_percent']:+.2f}%|{c['total_crossings']:,}|{c['pooled_reduction_percent']:+.2f}%|")
    lines.extend(["", "往復比は `100×(往復の交差数−循環の交差数)/往復の交差数`。正なら循環で交差が減少、負なら増加。グラフごとの率の平均ではなく、合計交差数から計算する。", "",
                  "## 今回の読み取り", ""])
    for metric, label in (("final_crossings", "最後の配置を採用"), ("guarded_crossings", "途中の最良配置を保存")):
        phrases = []
        for method, name in (("cyclic", "各ペア1回の循環"), ("current_cyclic", "各ペア5回の循環")):
            r = overall[(metric, method)]
            change = "減少" if r["pooled_reduction_percent"] >= 0 else "増加"
            phrases.append(f"{name}は{abs(r['pooled_reduction_percent']):.2f}%{change}")
        lines.append(f"- {label}すると、往復に対して{'、'.join(phrases)}。")
    r = overall[("final_crossings", "cyclic")]
    lines.append(f"- 指定された各ペア1回の循環は、最後の配置で改善{r['improved']}・同率{r['equal']}・悪化{r['worsened']}。全ケースで良くなる方法ではない。")
    if r["absolute_reduction_ci_low"] <= 0 <= r["absolute_reduction_ci_high"]:
        lines.append("- 最後の配置での平均削減数の95%区間は0を含むため、平均的な優位性が確立したとは言えない。")
    lines.extend(["", "## 図の読み方", "",
                  "![比較図](sweep_comparison.png)", "",
                  "- 上段：処理終了時の配置を採用した結果。下段：途中で得た最良配置を保存した結果。",
                  "- 左列：頂点数ごとの平均交差数。低いほど良い。各サイズを同数のseedで比較。",
                  "- 右列：往復からの合計交差数の削減率。0より上なら循環が改善、下なら悪化。",
                  "- 灰＝往復、青＝階層方向に何周も循環（各ペア1回）、橙＝各ペアで5回処理してから進む現行実装。",
                  "- 探索中の推移は別図 `sweep_trajectory.png`。回転後処理前の最良値を記録した曲線。上の比較図は回転後処理まで含めた交差数。", "",
                  "## 頂点数別の結果", ""])
    for metric, title in (("final_crossings", "最後の配置"), ("guarded_crossings", "途中の最良配置を保存")):
        lines.extend([f"### {title}", "", "|頂点数|件数|往復 平均交差数|循環1回 平均|削減率|改善/同率/悪化|循環5回 平均|削減率|", "|---:|---:|---:|---:|---:|---:|---:|---:|"])
        for n in ns:
            vals = [next(r for r in summaries if r["metric"] == metric and r["scope"] == f"n={n}" and r["method"] == m) for m in base.METHODS]
            a, b, c = vals
            lines.append(f"|{n}|{a['graphs']}|{a['mean_crossings']:.1f}|{b['mean_crossings']:.1f}|{b['pooled_reduction_percent']:+.2f}%|{b['improved']}/{b['equal']}/{b['worsened']}|{c['mean_crossings']:.1f}|{c['pooled_reduction_percent']:+.2f}%|")
        lines.append("")
    lines.extend(["## 全体の勝敗と不確実性", "", "|配置|循環の方法|改善/同率/悪化|平均削減数の95%区間|", "|---|---|---:|---:|"])
    for metric, title in (("final_crossings", "最後の配置"), ("guarded_crossings", "最良配置を保存")):
        for method in ("cyclic", "current_cyclic"):
            r = overall[(metric, method)]
            lines.append(f"|{title}|{LABELS[method]}|{r['improved']}/{r['equal']}/{r['worsened']}|[{r['absolute_reduction_ci_low']:.2f}, {r['absolute_reduction_ci_high']:.2f}]|")
    lines.extend(["", "95%区間はグラフ単位の対応差をbootstrap 10,000回（seed=20261006）で推定。区間が0を含む場合、平均的な優位性が確立したとは言えない。勝敗の件数と合計削減率は異なる指標なので併記する。", "",
                  "## 比較条件", "",
                  "- 最小トーラス辺数とそれを達成する最小階層数を二分探索し、diff_squareで階層割当。各ケースで一度だけ前処理し、全手法で同じ階層・ダミー辺・barycenter初期順序・巻き数を共有。",
                  "- 層数Lに対し、全手法の2層sifting呼出し回数を5(2L−1)に固定。循環1回は順方向の全隣接ペアを繰り返す。往復は順方向と逆方向の全隣接ペアを交互に処理。どちらも末尾・先頭のトーラス境界を含み、予算で停止する。",
                  "- 現行の循環は各ペアを5回処理し、順方向1周＋最後のペアを除くもう1周。繰り返し回数の配置も異なるため、方向のみの比較は青と灰で行う。",
                  "- すべて同じ2層sifting・巻き数最適化・ダミー辺重み・回転後処理を使用。最良配置保存では初期配置も候補に含め、回転後処理による悪化を採用しない。",
                  "- 前処理は逐次実行。交差削減は逐次実行と3手法の並列実行が混在するが、各手法は独立した同一入力のコピーから同じ処理を行う。raw_results.csvのexecution_workersで実行方式を記録。",
                  "- 実行時間は逐次・並列が混在するため参考記録扱い。軌跡探索（各処理後の交差計数・最良状態保存を含む）を測り、前処理・回転後処理・保存を除外。今回の図と結論は交差数についての比較。", "",
                  "## 適用範囲", "",
                  "これは指定WSモデル・時計回りの有向化・固定処理予算での結果。実ネットワークや別の向き付けへの一般化、各手法の理論的優位性を示すものではない。以前の最大50頂点の実験からは生成条件も変わっているため、交差数の増減を頂点数だけの効果として扱わない。", "",
                  "## 再現と保存データ", "", "```sh", "PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-sweep-mpl ./theme2026-saku/bin/python experiments/evaluate_torus_sweep_ws100.py --resume --workers 3", "```", "",
                  "`--summarize-only` はCSVから図と集計だけを再生成。`--quick` は10頂点・100頂点のseed=0を別フォルダで測定。",
                  "`raw_results.csv`、`summary.csv`、`traces.csv`、`embeddings.jsonl`（入力と共通初期配置）、`metadata.json`、比較図と推移図のPNG/SVGを保存。旧実験は親フォルダに保持。"])
    (output / "SWEEP_DIRECTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def artifacts(rows, traces, output):
    for row in rows:
        row.setdefault("execution_workers", 1)
    rows.sort(key=lambda r: (r["nodes"], r["seed"], base.METHODS.index(r["method"])))
    case_order = {r["case_id"]: (r["nodes"], r["seed"]) for r in rows}
    traces.sort(key=lambda t: (*case_order[t["case_id"]], base.METHODS.index(t["method"]), t["step"]))
    base.write_csv(output / "raw_results.csv", rows)
    base.write_csv(output / "traces.csv", traces)
    summaries = summarize(rows)
    base.write_csv(output / "summary.csv", summaries)
    write_report(rows, summaries, output)
    plot(rows, summaries, traces, output)
    print("RESULT", json.dumps([{key: r[key] for key in ("metric", "method", "graphs", "total_crossings", "pooled_reduction_percent", "improved", "equal", "worsened")} for r in summaries if r["scope"] == "all"], ensure_ascii=False), flush=True)


def run(quick=False, resume=False, summarize_only=False, workers=1):
    rounds = 5
    output = OUTPUT / "quick" if quick else OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    if summarize_only:
        artifacts(base.read_results(output / "raw_results.csv"), base.read_results(output / "traces.csv"), output)
        return
    config = {"rounds": rounds, "parameters": parameters(quick), "generator": "generate_watts_strogatz_graph",
              "radial_source_sha256": hashlib.sha256(Path(base.radial.__file__).read_bytes()).hexdigest(),
              "generator_source_sha256": hashlib.sha256((base.ROOT / "src/lib/generate_torus_graph.py").read_bytes()).hexdigest()}
    meta_path = output / "metadata.json"
    if resume and meta_path.exists() and json.loads(meta_path.read_text()) != config:
        raise ValueError("Saved experiment configuration differs; use a fresh output")
    meta_path.write_text(json.dumps(config, indent=2) + "\n")
    embedding_path = output / "embeddings.jsonl"
    # The size-check pilot uses the same conditions; preserve those measurements.
    pilot = OUTPUT / "quick"
    if resume and not quick and not (output / "raw_results.csv").exists() and (pilot / "raw_results.csv").exists():
        pilot_config = json.loads((pilot / "metadata.json").read_text())
        common = ("rounds", "generator", "radial_source_sha256", "generator_source_sha256")
        if all(pilot_config[key] == config[key] for key in common):
            pilot_rows = base.read_results(pilot / "raw_results.csv")
            done_keys = {r["case_id"] for r in pilot_rows}
            pilot_embeddings = [e for e in map(json.loads, (pilot / "embeddings.jsonl").read_text().splitlines()) if e["case_id"] in done_keys]
            embedding_path.write_text("".join(json.dumps(e) + "\n" for e in pilot_embeddings))
            base.write_csv(output / "raw_results.csv", pilot_rows)
            base.write_csv(output / "traces.csv", base.read_results(pilot / "traces.csv"))
    embeddings = {}
    rows, traces = [], []
    if resume and embedding_path.exists():
        embeddings = {e["case_id"]: e for e in map(json.loads, embedding_path.read_text().splitlines())}
    if resume and (output / "raw_results.csv").exists():
        rows = base.read_results(output / "raw_results.csv")
        traces = base.read_results(output / "traces.csv")
    done = {r["case_id"] for r in rows}
    for row in rows:
        row.setdefault("execution_workers", 1)
    traces = [t for t in traces if t["case_id"] in done]
    for key in done:
        if {r["method"] for r in rows if r["case_id"] == key} != set(base.METHODS):
            raise ValueError(f"Incomplete result for {key}")
    pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else nullcontext(None)
    with pool as executor, embedding_path.open("a" if resume else "w") as stream:
        for index, parameter in enumerate(config["parameters"]):
            key = case_id(parameter)
            if key in done:
                print(f"reuse {index+1}/{len(config['parameters'])} {key}", flush=True)
                continue
            if key not in embeddings:
                print(f"prepare {index+1}/{len(config['parameters'])} {key}", flush=True)
                embeddings[key] = prepare(parameter)
                stream.write(json.dumps(embeddings[key]) + "\n")
                stream.flush()
            embedding = embeddings[key]
            print(f"sift {key}: layers={len(embedding['layers'])} dummy_nodes={len(embedding['dummy_nodes'])} prep={embedding['preparation_seconds']:.2f}s", flush=True)
            case_rows, case_traces = evaluate_case(embedding, index, rounds, executor, workers)
            rows.extend(case_rows)
            traces.extend(case_traces)
            # The result CSV serves as the completed-case marker on resume.
            for name, values in (("traces", traces), ("raw_results", rows)):
                temporary = output / f"{name}.csv.tmp"
                base.write_csv(temporary, values)
                temporary.replace(output / f"{name}.csv")
            print(f"done {index+1}/{len(config['parameters'])} {key} " + str({r['method']: (r['final_crossings'], r['guarded_crossings']) for r in case_rows}), flush=True)
    artifacts(rows, traces, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--workers", type=int, choices=(1, 3), default=1,
                        help="Number of independent processes for the three schedules")
    args = parser.parse_args()
    run(args.quick, args.resume, args.summarize_only, args.workers)
