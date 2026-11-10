"""通常の杉山法と提案トーラス法を、同一グラフ上の交差数で比較する。

デフォルト設計は 5 頂点数 × 2 向き付け × 10 seed = 100 グラフ。
描画は行わず、各手法の交差削減終了直後の交差数を測る。
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
import time
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from crossing_reduction.radial import (  # noqa: E402
    count_radial_crossings,
    radial_sifting_global_guard_heuristic,
)
from sugiyama_layout.crossing_reduction import (  # noqa: E402
    count_crossings,
    reduce_crossings,
)
from sugiyama_layout.cycle_removal import remove_cycles  # noqa: E402
from sugiyama_layout.dummy_insertion import insert_dummy_nodes  # noqa: E402
from sugiyama_layout.layer_assignment import assign_layers  # noqa: E402
from layer_assignment.torus_balance import balance_layer_assignment  # noqa: E402
from layer_assignment.torus_binary_search import (  # noqa: E402
    find_minimum_torus_configuration,
)


NODE_COUNTS = (10, 20, 30, 40, 50)
ORIENTATIONS = ("random", "clockwise")
SEEDS = tuple(range(10))
NEIGHBOR_COUNT = 4
REWIRING_PROBABILITY = 0.25
PROPOSED_ROUNDS = 5
SUGIYAMA_SWEEPS = 12
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 20260731
OUTPUT_DIR = ROOT / "experiments/results/framework_crossings"


def generate_graph(nodes: int, seed: int, orientation: str):
    """同じ WS 無向構造を、指定方法で再現可能に有向化する。"""
    graph = nx.watts_strogatz_graph(
        nodes, NEIGHBOR_COUNT, REWIRING_PROBABILITY, seed=seed
    )
    rng = random.Random(seed)
    edges = []
    for first, second in sorted(graph.edges()):
        if orientation == "random":
            edge = (first, second) if rng.random() < 0.5 else (second, first)
        elif orientation == "clockwise":
            clockwise = (second - first) % nodes
            counterclockwise = (first - second) % nodes
            edge = (first, second) if clockwise <= counterclockwise else (second, first)
        else:
            raise ValueError(f"unknown orientation: {orientation}")
        edges.append(edge)
    return tuple(graph.nodes()), tuple(edges)


def evaluate_sugiyama(vertices, edges):
    started = time.perf_counter()
    acyclic = remove_cycles(vertices, edges)
    ranks = assign_layers(acyclic.nodes, acyclic.edges)
    hierarchy = insert_dummy_nodes(acyclic.nodes, acyclic.edges, ranks)
    initial = count_crossings(hierarchy.layers, hierarchy.edges)
    order = reduce_crossings(
        hierarchy.layers, hierarchy.edges, sweeps=SUGIYAMA_SWEEPS
    )
    final = count_crossings(order, hierarchy.edges)
    return initial, final, time.perf_counter() - started, len(hierarchy.dummy_nodes)


def evaluate_proposed(vertices, edges):
    started = time.perf_counter()
    layer_count, torus_count, _ = find_minimum_torus_configuration(vertices, edges)
    y_val, t_val, layers, _ = balance_layer_assignment(
        vertices, edges, torus_count, layer_count, "diff_square"
    )
    if not y_val:
        raise RuntimeError("proposed layer assignment failed")
    order, dummy_layers, dummy_edges, _dummy_torus, psi = (
        radial_sifting_global_guard_heuristic(
            vertices, edges, layers, t_val, rounds=PROPOSED_ROUNDS
        )
    )
    final = count_radial_crossings(order, psi, dummy_layers, dummy_edges)
    return (
        final,
        time.perf_counter() - started,
        sum(map(len, dummy_layers.values())) - len(vertices),
        layer_count,
        torus_count,
    )


def bootstrap_mean_ci(values):
    """ケースを標本単位にした paired bootstrap の95%区間。"""
    if not values:
        return None, None
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(values)
    means = sorted(
        statistics.mean(values[rng.randrange(size)] for _ in range(size))
        for _ in range(BOOTSTRAP_REPETITIONS)
    )
    return means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def summarize(group):
    differences = [r["sugiyama_crossings"] - r["proposed_crossings"] for r in group]
    valid_percent = [
        100 * difference / r["sugiyama_crossings"]
        for r, difference in zip(group, differences)
        if r["sugiyama_crossings"] > 0
    ]
    low, high = bootstrap_mean_ci(valid_percent)
    sugiyama_total = sum(r["sugiyama_crossings"] for r in group)
    proposed_total = sum(r["proposed_crossings"] for r in group)
    return {
        "graphs": len(group),
        "sugiyama_mean": statistics.mean(r["sugiyama_crossings"] for r in group),
        "proposed_mean": statistics.mean(r["proposed_crossings"] for r in group),
        "mean_absolute_reduction": statistics.mean(differences),
        "mean_relative_reduction_percent": statistics.mean(valid_percent)
        if valid_percent
        else None,
        "relative_reduction_ci_low": low,
        "relative_reduction_ci_high": high,
        "pooled_reduction_percent": 100 * (sugiyama_total - proposed_total) / sugiyama_total
        if sugiyama_total
        else None,
        "improved": sum(value > 0 for value in differences),
        "equal": sum(value == 0 for value in differences),
        "worsened": sum(value < 0 for value in differences),
        "zero_baselines": sum(r["sugiyama_crossings"] == 0 for r in group),
    }


def run(node_counts=NODE_COUNTS, orientations=ORIENTATIONS, seeds=SEEDS):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for nodes in node_counts:
        for orientation in orientations:
            for seed in seeds:
                vertices, edges = generate_graph(nodes, seed, orientation)
                s_initial, s_final, s_time, s_dummy = evaluate_sugiyama(vertices, edges)
                p_final, p_time, p_dummy, layers, torus = evaluate_proposed(
                    vertices, edges
                )
                row = {
                    "nodes": nodes,
                    "orientation": orientation,
                    "seed": seed,
                    "edges": len(edges),
                    "sugiyama_initial_crossings": s_initial,
                    "sugiyama_crossings": s_final,
                    "proposed_crossings": p_final,
                    "absolute_reduction": s_final - p_final,
                    "relative_reduction_percent":
                        100 * (s_final - p_final) / s_final if s_final else "",
                    "sugiyama_seconds": s_time,
                    "proposed_seconds": p_time,
                    "sugiyama_dummy_nodes": s_dummy,
                    "proposed_dummy_nodes": p_dummy,
                    "proposed_layer_count": layers,
                    "proposed_torus_edges": torus,
                }
                rows.append(row)
                print(
                    f"n={nodes:>2} {orientation:<9} seed={seed} E={len(edges):>3} "
                    f"crossings: Sugiyama={s_final}, proposed={p_final}",
                    flush=True,
                )

    raw_path = OUTPUT_DIR / "raw_results.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    summaries = []
    for nodes in node_counts:
        group = [row for row in rows if row["nodes"] == nodes]
        summaries.append({"scope": f"n={nodes}", **summarize(group)})
    for orientation in orientations:
        group = [row for row in rows if row["orientation"] == orientation]
        summaries.append({"scope": f"orientation={orientation}", **summarize(group)})
    summaries.append({"scope": "all", **summarize(rows)})
    summary_path = OUTPUT_DIR / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=summaries[0])
        writer.writeheader()
        writer.writerows(summaries)

    write_report(rows, summaries)
    return rows, summaries


def fmt(value, digits=2):
    return "NA" if value is None else f"{value:.{digits}f}"


def write_report(rows, summaries):
    overall = summaries[-1]
    lines = [
        "# 既存杉山法と提案トーラス法の交差数比較",
        "",
        "## 実験計画と設定根拠",
        "",
        f"- グラフ数: **{len(rows)}**（5サイズ × 2向き付け × 10 seed）。区切りのよい総数100とし、各サイズを同数20にした。",
        f"- 頂点数: {', '.join(map(str, NODE_COUNTS))}。10から50まで10刻みで、小規模から中規模のサイズ効果を等間隔に観察する。",
        f"- 構造: Watts–Strogatz、平均次数 {NEIGHBOR_COUNT}、再配線確率 {REWIRING_PROBABILITY}。辺数を約2nに保ち、サイズと密度の交絡を抑えつつ、規則性とランダム性を併せ持つ連結構造を使う。",
        "- 向き付け: random と clockwise を各10件。提案法が利用する円環構造に沿う向きだけに偏らないかを確認する。",
        "- 対応比較: 各ケースの頂点・有向辺・seedを固定し、両手法へ同一入力を渡す。",
        f"- 既存法: cycle removal + longest-path layering + dummy insertion + median/transpose（{SUGIYAMA_SWEEPS} sweeps、既存実装の既定値）。",
        f"- 提案法: 最小トーラス辺探索 + diff_square balance + global-guard radial sifting（{PROPOSED_ROUNDS} rounds、既存実験の既定値）。",
        "- 主指標: `100 × (杉山法交差数 − 提案法交差数) / 杉山法交差数`。正なら提案法が削減。分母0のケースは相対率から除外し、件数を別掲する。",
        f"- 不確実性: 同一ケースの差を保つ paired bootstrap {BOOTSTRAP_REPETITIONS:,} 回（固定seed={BOOTSTRAP_SEED}）で平均相対削減率の95%区間を求める。",
        "",
        "## 結果",
        "",
        "|集計範囲|件数|杉山 平均|提案 平均|平均削減数|平均削減率 (95% CI)|全交差の削減率|改善/同率/悪化|杉山0件|",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"|{row['scope']}|{row['graphs']}|{row['sugiyama_mean']:.2f}|"
            f"{row['proposed_mean']:.2f}|{row['mean_absolute_reduction']:.2f}|"
            f"{fmt(row['mean_relative_reduction_percent'])}% "
            f"[{fmt(row['relative_reduction_ci_low'])}, {fmt(row['relative_reduction_ci_high'])}]|"
            f"{fmt(row['pooled_reduction_percent'])}%|{row['improved']}/{row['equal']}/{row['worsened']}|"
            f"{row['zero_baselines']}|"
        )
    lines += [
        "",
        f"全{overall['graphs']}ケースの生データは `raw_results.csv`、機械可読な集計は `summary.csv`。",
        "",
        "## 解釈上の注意",
        "",
        "交差数は各手法が作る proper hierarchy（長辺をダミー辺に分割後）で数える。提案法はトーラス基本領域、杉山法は平面階層領域なので、これは各描画面で可視化される交差の操作的比較であり、同一曲面上の位相的最小交差数の比較ではない。単一のグラフモデルだけを用いるため、他の次数分布・実ネットワークへの一般化は別実験が必要である。",
    ]
    (OUTPUT_DIR / "FRAMEWORK_CROSSINGS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick", action="store_true", help="動作確認用に n=10、各向きseed=0だけ実行"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.quick:
        run(node_counts=(10,), seeds=(0,))
    else:
        run()
