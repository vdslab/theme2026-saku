"""階層数の二分探索を全探索と照合する実験。"""

from __future__ import annotations

import csv
import math
import statistics
import time
from pathlib import Path

from layer_assignment.torus_binary_search import find_minimum_torus_configuration
from layer_assignment.torus_two_stage import minimize_torus_edges
from lib.generate_torus_graph import (
    generate_cyclic_graph,
    generate_dag,
    generate_mixed_graph,
    generate_random_connected_graph,
)


NODE_COUNTS = (8, 12, 20, 30)
FAMILIES = ("dag", "mixed", "cyclic", "random")
SEEDS = (0, 1, 2)
TARGET_AVERAGE_DEGREE = 4.0

OUTPUT_DIR = Path("experiments/results/layer_count_search")
RAW_CSV = OUTPUT_DIR / "raw_results.csv"
CURVES_CSV = OUTPUT_DIR / "torus_count_curves.csv"
SUMMARY_MD = OUTPUT_DIR / "LAYER_COUNT_SEARCH.md"


def edge_probability(nodes: int) -> float:
    return min(1.0, TARGET_AVERAGE_DEGREE / max(1, nodes - 1))


def generate_graph(family: str, nodes: int, seed: int):
    probability = edge_probability(nodes)
    if family == "dag":
        return generate_dag(nodes, edge_prob=probability, seed=seed)
    if family == "mixed":
        return generate_mixed_graph(
            nodes, edge_prob=probability, cycle_prob=0.3, seed=seed
        )
    if family == "cyclic":
        return generate_cyclic_graph(
            nodes, num_cycles=max(1, nodes // 10), edge_prob=probability, seed=seed
        )
    if family == "random":
        return generate_random_connected_graph(
            nodes, edge_prob=probability, seed=seed
        )
    raise ValueError(f"unknown family: {family}")


def exhaustive_search(vertices, edges):
    started = time.perf_counter()
    curve = []
    for layer_count in range(1, len(vertices) + 1):
        _y, _t, _layers, runtime, torus_count = minimize_torus_edges(
            vertices, edges, layer_count
        )
        curve.append((layer_count, torus_count, runtime))

    feasible = [(layer_count, count) for layer_count, count, _ in curve if count is not None]
    target = min(count for _, count in feasible)
    optimal_layer_count = min(
        layer_count for layer_count, count in feasible if count == target
    )
    return optimal_layer_count, target, time.perf_counter() - started, curve


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    curve_rows = []

    for nodes in NODE_COUNTS:
        for family in FAMILIES:
            for seed in SEEDS:
                vertices, edges = generate_graph(family, nodes, seed)
                edges = sorted(set(edges))
                exact_l, exact_t, exhaustive_seconds, curve = exhaustive_search(
                    vertices, edges
                )
                proposed_l, proposed_t, proposed_seconds = (
                    find_minimum_torus_configuration(vertices, edges)
                )

                counts = {layer_count: count for layer_count, count, _ in curve}
                fixed_3 = counts.get(3)
                fixed_5 = counts.get(5)
                sqrt_l = min(nodes, max(1, math.ceil(math.sqrt(nodes))))
                sqrt_t = counts.get(sqrt_l)
                row = {
                    "nodes": nodes,
                    "family": family,
                    "seed": seed,
                    "edges": len(edges),
                    "edge_probability": edge_probability(nodes),
                    "exact_layer_count": exact_l,
                    "exact_torus_count": exact_t,
                    "proposed_layer_count": proposed_l,
                    "proposed_torus_count": proposed_t,
                    "layer_count_match": proposed_l == exact_l,
                    "torus_count_match": proposed_t == exact_t,
                    "exhaustive_seconds": exhaustive_seconds,
                    "proposed_seconds": proposed_seconds,
                    "fixed_3_torus_count": fixed_3,
                    "fixed_5_torus_count": fixed_5,
                    "sqrt_layer_count": sqrt_l,
                    "sqrt_torus_count": sqrt_t,
                }
                rows.append(row)
                for layer_count, torus_count, solver_seconds in curve:
                    curve_rows.append(
                        {
                            "nodes": nodes,
                            "family": family,
                            "seed": seed,
                            "edges": len(edges),
                            "layer_count": layer_count,
                            "torus_count": torus_count,
                            "solver_seconds": solver_seconds,
                        }
                    )
                print(
                    f"n={nodes:>2} {family:<6} seed={seed} E={len(edges):>3} "
                    f"exact=({exact_l},{exact_t}) proposed=({proposed_l},{proposed_t})",
                    flush=True,
                )

    with RAW_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with CURVES_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=curve_rows[0].keys())
        writer.writeheader()
        writer.writerows(curve_rows)

    layer_matches = sum(row["layer_count_match"] for row in rows)
    torus_matches = sum(row["torus_count_match"] for row in rows)
    speedups = [
        row["exhaustive_seconds"] / row["proposed_seconds"]
        for row in rows
        if row["proposed_seconds"] > 0
    ]

    def baseline_stats(key: str):
        valid = [row for row in rows if row[key] is not None]
        optimal = sum(row[key] == row["exact_torus_count"] for row in valid)
        excess = [row[key] - row["exact_torus_count"] for row in valid]
        return len(valid), len(rows) - len(valid), optimal, statistics.mean(excess)

    fixed_3 = baseline_stats("fixed_3_torus_count")
    fixed_5 = baseline_stats("fixed_5_torus_count")
    sqrt_result = baseline_stats("sqrt_torus_count")
    lines = [
        "# 階層数自動決定の全探索照合",
        "",
        f"- グラフ数: {len(rows)}",
        f"- 頂点数: {', '.join(map(str, NODE_COUNTS))}",
        f"- グラフ族: {', '.join(FAMILIES)}",
        f"- seed: {', '.join(map(str, SEEDS))}",
        f"- 目標平均次数: {TARGET_AVERAGE_DEGREE}",
        "",
        "## 正当性と速度",
        "",
        f"- 最小トーラス辺数一致: {torus_matches}/{len(rows)}",
        f"- それを達成する最小階層数も一致: {layer_matches}/{len(rows)}",
        f"- 提案手法の実行時間中央値: {statistics.median(row['proposed_seconds'] for row in rows):.4f} 秒",
        f"- 全探索の実行時間中央値: {statistics.median(row['exhaustive_seconds'] for row in rows):.4f} 秒",
        f"- 全探索に対する高速化率中央値: {statistics.median(speedups):.2f} 倍",
        "",
        "## 固定階層数との比較",
        "",
        "|方法|実行可能|実行不能|最小トーラス辺数を達成|余分なトーラス辺数の平均|",
        "|---|---:|---:|---:|---:|",
        f"|k=3|{fixed_3[0]}|{fixed_3[1]}|{fixed_3[2]}|{fixed_3[3]:.3f}|",
        f"|k=5|{fixed_5[0]}|{fixed_5[1]}|{fixed_5[2]}|{fixed_5[3]:.3f}|",
        f"|k=ceil(sqrt(n))|{sqrt_result[0]}|{sqrt_result[1]}|{sqrt_result[2]}|{sqrt_result[3]:.3f}|",
        "",
        "詳細は `raw_results.csv`、kごとの曲線は `torus_count_curves.csv`。",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
