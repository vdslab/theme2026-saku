"""Compare torus sifting schedules from identical saved initial embeddings.

PYTHONPATH=src ./theme2026-saku/bin/python experiments/evaluate_torus_sweep_direction.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import old_torus_layout.crossing_reduction.radial as radial
from old_torus_layout.layer_assignment.torus_balance import balance_layer_assignment
from old_torus_layout.lib.generate_torus_graph import generate_watts_strogatz_graph

OUTPUT = ROOT / "experiments/results/torus_sweep_direction"
PARAMETERS = ROOT / "experiments/results/layer_count_search/raw_results.csv"
METHODS = ("alternating", "cyclic", "current_cyclic")
LABELS = {"alternating": "往復", "cyclic": "全体を循環", "current_cyclic": "現行の循環"}


def schedule(layers, method, rounds=5):
    forward = radial._forward_layer_pairs(layers)
    if not forward:
        return []
    budget = rounds * (2 * len(layers) - 1)
    if method == "current_cyclic":
        return [pair for pair in forward + forward[:-1] for _ in range(rounds)]
    if method == "cyclic":
        cycle = forward
    elif method == "alternating":
        cycle = forward + radial._backward_layer_pairs(layers)
    else:
        raise ValueError(method)
    return list(itertools.islice(itertools.cycle(cycle), budget))


def evaluate(initial_order, initial_psi, layers, edges, dummy_nodes, pairs):
    order = radial._copy_order(initial_order)
    psi = dict(initial_psi)
    best_order, best_psi = radial._copy_order(order), dict(psi)
    best = radial._count_all_crossings(order, psi, layers, edges)
    trace = [{"step": 0, "crossings": best, "best_crossings": best, "elapsed_seconds": 0}]
    started = time.perf_counter()
    for step, (fixed, free) in enumerate(pairs, 1):
        radial._sift_two_layer_pair(fixed, free, order, psi, edges, dummy_nodes=dummy_nodes)
        count = radial._count_all_crossings(order, psi, layers, edges)
        if count < best:
            best = count
            best_order, best_psi = radial._copy_order(order), dict(psi)
        trace.append({"step": step, "fixed_layer": fixed, "free_layer": free,
                      "crossings": count, "best_crossings": best,
                      "elapsed_seconds": time.perf_counter() - started})
    trajectory_seconds = time.perf_counter() - started
    radial._postprocess_sifting_rotations(order, psi, layers, edges)
    final = radial._count_all_crossings(order, psi, layers, edges)
    radial._postprocess_sifting_rotations(best_order, best_psi, layers, edges)
    guarded = min(best, radial._count_all_crossings(best_order, best_psi, layers, edges))
    return {"final_crossings": final, "guarded_crossings": guarded,
            "local_passes": len(pairs), "trajectory_seconds": trajectory_seconds}, trace


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def bootstrap(values):
    rng = random.Random(20261006)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(10000))
    return means[250], means[9750]


def summarize(rows, metric, scope):
    cases = {}
    for row in rows:
        cases.setdefault(row["case_id"], {})[row["method"]] = row
    result = []
    for method in METHODS:
        baseline = [case["alternating"][metric] for case in cases.values()]
        values = [case[method][metric] for case in cases.values()]
        differences = [b - v for b, v in zip(baseline, values)]
        percentages = [100 * (b - v) / b for b, v in zip(baseline, values) if b]
        low, high = bootstrap(differences)
        result.append({"scope": scope, "metric": metric, "method": method,
                       "graphs": len(cases), "total_crossings": sum(values),
                       "mean_crossings": statistics.mean(values),
                       "median_crossings": statistics.median(values),
                       "pooled_reduction_percent": 100 * sum(differences) / sum(baseline) if sum(baseline) else 0,
                       "mean_relative_reduction_percent": statistics.mean(percentages) if percentages else 0,
                       "zero_baselines": sum(b == 0 for b in baseline),
                       "mean_absolute_reduction": statistics.mean(differences),
                       "absolute_reduction_ci_low": low, "absolute_reduction_ci_high": high,
                       "improved": sum(d > 0 for d in differences),
                       "equal": sum(d == 0 for d in differences),
                       "worsened": sum(d < 0 for d in differences),
                       "median_trajectory_ms": 1000 * statistics.median(case[method]["trajectory_seconds"] for case in cases.values())})
    return result


def artifacts(rows, traces, output, rounds):
    summaries = []
    for metric in ("final_crossings", "guarded_crossings"):
        summaries.extend(summarize(rows, metric, "all"))
        for n in sorted({r["nodes"] for r in rows}):
            summaries.extend(summarize([r for r in rows if r["nodes"] == n], metric, f"n={n}"))
        for k in sorted({r["neighbors"] for r in rows}):
            summaries.extend(summarize([r for r in rows if r["neighbors"] == k], metric, f"neighbors={k}"))
        for p in sorted({r["rewiring_probability"] for r in rows}):
            summaries.extend(summarize([r for r in rows if r["rewiring_probability"] == p], metric, f"p={p}"))
    write_csv(output / "summary.csv", summaries)
    count = len(rows) // len(METHODS)
    lines = ["# トーラス交差削減：往復と循環の比較", "",
             f"同一初期配置での対応比較：{count}グラフ。WS、頂点数{sorted({r['nodes'] for r in rows})}、近傍数{sorted({r['neighbors'] for r in rows})}、再配線確率{sorted({r['rewiring_probability'] for r in rows})}、seed={sorted({r['seed'] for r in rows})}。円環上の短い時計回り方向に有向化。", "",
             "## 比較条件", "",
             "- 既存の階層数実験の全探索結果から最小階層数とトーラス辺数を読み、各グラフについてdiff_square階層割当を一度だけ求解。全手法で階層・ダミー辺・barycenter初期順序・初期巻き数を共有。",
             f"- 実際の層数をLとし、全手法の2層sifting呼出し回数を **{rounds}(2L−1)** に固定。rounds={rounds}。",
             "- 往復：順方向の全隣接ペア→逆方向の全隣接ペアを繰り返し、予算で停止。逆方向では固定層と自由層を入れ替える。双方ともトーラスの末尾→先頭境界を含む。",
             "- 全体を循環：順方向の全隣接ペアを繰り返し、同じ予算で停止。往復との違いは走査方向のみ。",
             "- 3層の例：循環は1→2、2→3、3→1、1→2…、往復は1→2、2→3、3→1、1→3、3→2、2→1…（矢印の始点が固定層、終点が自由層）。",
             f"- 現行の循環：各ペアで{rounds}回連続siftingし、順方向を1周＋最後のペアを除く1周。現行_run_siftingと同じ。こちらは方向と局所反復の配置が異なる。",
             "- すべて同じ現行2層sifting・ダミー辺重み・巻き数最適化・回転後処理を利用。過去実装の全体比較ではなく、走査スケジュールのアブレーション。",
             "- 最終状態（通常sifting）と、途中の全体最小交差状態を保持した結果（global guard）を別々に集計。後者は初期状態も候補に含める。両方に同じ回転後処理を適用し、guardでは後処理による悪化を採用しない。",
             "- 時間は交差削減の軌跡探索のみ（各処理後の交差計数・最良状態保存を含む）。前処理・回転後処理・CSV保存は除外。各条件1回測定であり参考値。実行順序はケースごとに循環させる。", "",
             "## 結果", ""]
    for metric, title in (("final_crossings", "最終状態"), ("guarded_crossings", "全体最良状態を保持（global guard）")):
        lines.extend([f"### {title}", "", "|方法|合計交差数|平均|中央値|往復比の合計削減率|改善/同率/悪化|平均削減数の95% CI|時間中央値(ms)|", "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for r in summaries:
            if r["scope"] == "all" and r["metric"] == metric:
                lines.append(f"|{LABELS[r['method']]}|{r['total_crossings']}|{r['mean_crossings']:.2f}|{r['median_crossings']:.1f}|{r['pooled_reduction_percent']:.2f}%|{r['improved']}/{r['equal']}/{r['worsened']}|[{r['absolute_reduction_ci_low']:.2f}, {r['absolute_reduction_ci_high']:.2f}]|{r['median_trajectory_ms']:.2f}|")
        lines.append("")
    lines.extend(["### 読み取り", ""])
    for metric, title in (("final_crossings", "最終状態"), ("guarded_crossings", "全体最良状態を保持した場合")):
        r = next(r for r in summaries if r["scope"] == "all" and r["metric"] == metric and r["method"] == "cyclic")
        direction = "減少" if r["pooled_reduction_percent"] >= 0 else "増加"
        lines.append(f"- {title}：全体を循環する方法は往復に対して合計交差数が{abs(r['pooled_reduction_percent']):.2f}%{direction}。ケース別では改善{r['improved']}・同率{r['equal']}・悪化{r['worsened']}。合計とケースごとの勝敗は異なる集計なので、両方を併記する。")
        if r["absolute_reduction_ci_low"] <= 0 <= r["absolute_reduction_ci_high"]:
            lines.append("  平均削減数の95%区間は0を含むため、平均的な優位性が確立したとは言えない。")
    lines.extend(["", "図の凡例：alternating＝往復、cyclic＝全体を循環（指定された方法）、current_cyclic＝現行の循環。", ""])
    lines.extend(["正の削減率・削減数は循環の改善を示す。95%区間はグラフ単位の対応差をbootstrap 10,000回（seed=20261006）で推定。初期交差0のグラフも絶対差・勝敗・合計に含む。相対率の平均では往復の交差数0を除外し、summary.csvに分母0件数も保存。", "",
                  "このグラフ生成条件における結果であり、循環が常に良いことを意味しない。時計回り以外の向き付け・実ネットワーク・より多い処理予算は未評価。呼出し回数が同じでも、自由層のサイズによって計算量は異なる。", "",
                  "## 再現", "", "```sh", "PYTHONPATH=src MPLCONFIGDIR=/tmp/torus-sweep-mpl ./theme2026-saku/bin/python experiments/evaluate_torus_sweep_direction.py", "```", "",
                  "保存済みembeddingで再実行する場合は --reuse-embeddings を付ける（Gurobi前処理を省略）。--summarize-onlyは保存済みCSVから集計・図だけを再生成。--quickは先頭2ケースを別フォルダへ出力。", "",
                  "raw_results.csv（各ケースの結果）、summary.csv（全体・頂点数・密度・再配線確率別集計）、traces.csv（全処理の推移）、embeddings.jsonl（入力と初期配置）、sweep_comparison.png/.svg（比較図）。"])
    (output / "SWEEP_DIRECTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot(rows, traces, output)


def plot(rows, traces, output):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/torus-sweep-mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"alternating": "#64748b", "cyclic": "#2563eb", "current_cyclic": "#db7b23"}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    for method in METHODS:
        group = [r for r in rows if r["method"] == method]
        ns = sorted({r["nodes"] for r in group})
        axes[0].plot(ns, [statistics.mean(r["final_crossings"] for r in group if r["nodes"] == n) for n in ns], "o-", label=method, color=colors[method])
        axes[1].plot(ns, [statistics.mean(r["guarded_crossings"] for r in group if r["nodes"] == n) for n in ns], "o-", label=method, color=colors[method])
        curves = {}
        for t in traces:
            if t["method"] == method:
                curves.setdefault(t["case_id"], []).append(t)
        xs = list(range(101))
        ys = [statistics.mean(curve[min(len(curve)-1, int(x/100 * (len(curve)-1)))]["best_crossings"] for curve in curves.values()) for x in xs]
        axes[2].plot(xs, ys, label=method, color=colors[method])
    for ax, title in zip(axes, ("Final state", "Global guard", "Best-so-far trajectory")):
        ax.set_title(title)
        ax.set_ylabel("Mean crossings")
        ax.grid(alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_xlabel("Original nodes")
    axes[1].set_xlabel("Original nodes")
    axes[2].set_xlabel("Local-pass budget consumed (%)")
    axes[2].legend(fontsize=8)
    fig.suptitle(f"Torus sifting schedules: {len(rows)//3} paired graphs, equal local-pass budgets")
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(output / f"sweep_comparison.{suffix}", dpi=180, facecolor="white")
    plt.close(fig)


def prepare_embedding(parameter):
    n, k, p, seed = int(parameter["nodes"]), int(parameter["neighbors"]), float(parameter["rewiring_probability"]), int(parameter["seed"])
    vertices, edges = generate_watts_strogatz_graph(n, k=k, p=p, seed=seed, ensure_connected=True)
    edges = sorted(set(edges))
    if len(edges) != int(parameter["edges"]):
        raise ValueError("Graph differs from source experiment")
    layer_count, torus_count = int(parameter["exact_layer_count"]), int(parameter["exact_torus_count"])
    y, t, assignment, _ = balance_layer_assignment(vertices, edges, torus_count, layer_count, "diff_square")
    if not y:
        raise RuntimeError("Layer assignment failed")
    original_nodes = set(vertices)
    dummy_v, dummy_e, dummy_l, _, _ = radial.insert_dummy_node(vertices, edges, assignment, t)
    layers = sorted(dummy_l)
    order = radial._initial_orders(dummy_l, layers, dummy_e)[0]
    psi = radial._compute_winding_numbers(dummy_e, order, dummy_l, layers)
    return {"case_id": f"n{n}_k{k}_p{p}_s{seed}", "nodes": n, "neighbors": k,
            "rewiring_probability": p, "seed": seed, "layer_count": layer_count,
            "torus_count": torus_count, "vertices": vertices, "original_edges": edges,
            "layers": layers, "order": [[layer, order[layer]] for layer in layers],
            "edges": dummy_e, "psi": [[list(e), value] for e, value in psi.items()],
            "dummy_nodes": sorted(set(dummy_v) - original_nodes)}


def read_results(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    int_keys = {"nodes", "neighbors", "seed", "layer_count", "torus_count", "rounds", "initial_crossings", "final_crossings", "guarded_crossings", "local_passes", "step", "fixed_layer", "free_layer", "crossings", "best_crossings"}
    float_keys = {"rewiring_probability", "trajectory_seconds", "elapsed_seconds"}
    for row in rows:
        for key, value in row.items():
            if value != "" and key in int_keys:
                row[key] = int(value)
            elif value != "" and key in float_keys:
                row[key] = float(value)
    return rows


def run(quick=False, reuse=False, rounds=5, summarize_only=False):
    output = OUTPUT / "quick" if quick else OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    if summarize_only:
        rows = read_results(output / "raw_results.csv")
        traces = read_results(output / "traces.csv")
        artifacts(rows, traces, output, rows[0]["rounds"])
        return
    embedding_path = output / "embeddings.jsonl"
    if reuse:
        embeddings = [json.loads(line) for line in embedding_path.read_text().splitlines()]
    else:
        with PARAMETERS.open() as stream:
            parameters = list(csv.DictReader(stream))
        if quick:
            parameters = parameters[:2]
        embeddings = []
        with embedding_path.open("w") as stream:
            for i, parameter in enumerate(parameters, 1):
                embedding = prepare_embedding(parameter)
                stream.write(json.dumps(embedding) + "\n")
                stream.flush()
                embeddings.append(embedding)
                print(f"prepare {i}/{len(parameters)} {embedding['case_id']}", flush=True)
    rows, traces = [], []
    for i, embedding in enumerate(embeddings):
        order = {layer: nodes for layer, nodes in embedding["order"]}
        psi = {tuple(edge): value for edge, value in embedding["psi"]}
        edges = [tuple(e) for e in embedding["edges"]]
        initial = radial._count_all_crossings(order, psi, embedding["layers"], edges)
        execution_order = METHODS[i % 3:] + METHODS[:i % 3]
        for method in execution_order:
            result, trace = evaluate(order, psi, embedding["layers"], edges, set(embedding["dummy_nodes"]), schedule(embedding["layers"], method, rounds))
            row = {key: embedding[key] for key in ("case_id", "nodes", "neighbors", "rewiring_probability", "seed", "layer_count", "torus_count")}
            row.update({"method": method, "rounds": rounds, "initial_crossings": initial, **result})
            rows.append(row)
            for t in trace:
                traces.append({"case_id": embedding["case_id"], "method": method, "step": t["step"],
                               "fixed_layer": t.get("fixed_layer", ""), "free_layer": t.get("free_layer", ""),
                               "crossings": t["crossings"], "best_crossings": t["best_crossings"], "elapsed_seconds": t["elapsed_seconds"]})
        print(f"evaluate {i+1}/{len(embeddings)} {embedding['case_id']} " + str({r['method']: (r['final_crossings'], r['guarded_crossings']) for r in rows[-3:]}), flush=True)
        write_csv(output / "raw_results.csv", rows)
    write_csv(output / "traces.csv", traces)
    (output / "metadata.json").write_text(json.dumps({"rounds": rounds, "graphs": len(embeddings), "source_parameters_sha256": hashlib.sha256(PARAMETERS.read_bytes()).hexdigest(), "radial_source_sha256": hashlib.sha256(Path(radial.__file__).read_bytes()).hexdigest(), "python": sys.version}, indent=2) + "\n")
    artifacts(rows, traces, output, rounds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--reuse-embeddings", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    run(args.quick, args.reuse_embeddings, args.rounds, args.summarize_only)
