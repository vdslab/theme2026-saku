"""Watts--Strogatzグラフで階層数の二分探索を全探索と照合する実験。"""

from __future__ import annotations

import csv
import math
import statistics
import time
from pathlib import Path

from layer_assignment.torus_binary_search import find_minimum_torus_configuration
from layer_assignment.torus_two_stage import minimize_torus_edges
from lib.generate_torus_graph import generate_watts_strogatz_graph


# 5頂点規模 × 2近傍数 × 2再配線確率 × 5 seed = 100グラフ。
# 元実験（最大30頂点、各条件3 seed、計48件）より、規模・生成条件・標本数を増やす。
NODE_COUNTS = (10, 20, 30, 40, 50)
NEIGHBOR_COUNTS = (2, 4)
REWIRING_PROBABILITIES = (0.1, 0.5)
SEEDS = tuple(range(5))

OUTPUT_DIR = Path("experiments/results/layer_count_search")
RAW_CSV = OUTPUT_DIR / "raw_results.csv"
CURVES_CSV = OUTPUT_DIR / "torus_count_curves.csv"
SUMMARY_CSV = OUTPUT_DIR / "summary.csv"
SUMMARY_MD = OUTPUT_DIR / "LAYER_COUNT_SEARCH.md"


def generate_graph(nodes: int, neighbors: int, rewiring: float, seed: int):
    """連結WSグラフを生成し、円環上の短い時計回り方向へ各辺を向ける。"""
    return generate_watts_strogatz_graph(
        nodes,
        k=neighbors,
        p=rewiring,
        seed=seed,
        ensure_connected=True,
    )


def exhaustive_search(vertices, edges):
    """k=1,...,|V|を厳密求解し、辞書式目的の正解を作る。"""
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


def baseline_stats(rows, key: str):
    valid = [row for row in rows if row[key] is not None]
    optimal = sum(row[key] == row["exact_torus_count"] for row in valid)
    excess = [row[key] - row["exact_torus_count"] for row in valid]
    return {
        "method": key.removesuffix("_torus_count"),
        "feasible": len(valid),
        "infeasible": len(rows) - len(valid),
        "optimal": optimal,
        "suboptimal": len(valid) - optimal,
        "mean_excess": statistics.mean(excess),
    }


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    curve_rows = []
    total = (
        len(NODE_COUNTS)
        * len(NEIGHBOR_COUNTS)
        * len(REWIRING_PROBABILITIES)
        * len(SEEDS)
    )

    case_number = 0
    for nodes in NODE_COUNTS:
        for neighbors in NEIGHBOR_COUNTS:
            for rewiring in REWIRING_PROBABILITIES:
                for seed in SEEDS:
                    case_number += 1
                    vertices, edges = generate_graph(nodes, neighbors, rewiring, seed)
                    edges = sorted(set(edges))
                    exact_l, exact_t, exhaustive_seconds, curve = exhaustive_search(
                        vertices, edges
                    )
                    proposed_l, proposed_t, proposed_seconds = (
                        find_minimum_torus_configuration(vertices, edges)
                    )

                    counts = {layer_count: count for layer_count, count, _ in curve}
                    existing_l = min(
                        nodes, max(1, math.ceil(math.sqrt(2 * nodes)))
                    )
                    row = {
                        "nodes": nodes,
                        "neighbors": neighbors,
                        "rewiring_probability": rewiring,
                        "seed": seed,
                        "edges": len(edges),
                        "exact_layer_count": exact_l,
                        "exact_torus_count": exact_t,
                        "proposed_layer_count": proposed_l,
                        "proposed_torus_count": proposed_t,
                        "layer_count_match": proposed_l == exact_l,
                        "torus_count_match": proposed_t == exact_t,
                        "exhaustive_seconds": exhaustive_seconds,
                        "proposed_seconds": proposed_seconds,
                        "fixed_3_torus_count": counts.get(3),
                        "fixed_5_torus_count": counts.get(5),
                        "existing_layer_count": existing_l,
                        "existing_torus_count": counts.get(existing_l),
                    }
                    rows.append(row)
                    for layer_count, torus_count, solver_seconds in curve:
                        curve_rows.append(
                            {
                                "nodes": nodes,
                                "neighbors": neighbors,
                                "rewiring_probability": rewiring,
                                "seed": seed,
                                "edges": len(edges),
                                "layer_count": layer_count,
                                "torus_count": torus_count,
                                "solver_seconds": solver_seconds,
                            }
                        )
                    print(
                        f"[{case_number:>3}/{total}] n={nodes:>2} k_ws={neighbors} "
                        f"p={rewiring:.1f} seed={seed} E={len(edges):>3} "
                        f"exact=({exact_l},{exact_t}) proposed=({proposed_l},{proposed_t})",
                        flush=True,
                    )

    write_csv(RAW_CSV, rows)
    write_csv(CURVES_CSV, curve_rows)

    layer_matches = sum(row["layer_count_match"] for row in rows)
    torus_matches = sum(row["torus_count_match"] for row in rows)
    speedups = [
        row["exhaustive_seconds"] / row["proposed_seconds"]
        for row in rows
        if row["proposed_seconds"] > 0
    ]
    summaries = [
        baseline_stats(rows, "fixed_3_torus_count"),
        baseline_stats(rows, "fixed_5_torus_count"),
        baseline_stats(rows, "existing_torus_count"),
        {
            "method": "proposed",
            "feasible": len(rows),
            "infeasible": 0,
            "optimal": torus_matches,
            "suboptimal": len(rows) - torus_matches,
            "mean_excess": statistics.mean(
                row["proposed_torus_count"] - row["exact_torus_count"] for row in rows
            ),
        },
    ]
    write_csv(SUMMARY_CSV, summaries)

    lines = [
        "# Watts--Strogatzグラフによる階層数自動決定の全探索照合",
        "",
        "## 実験設計",
        "",
        f"- グラフ数: {len(rows)}",
        f"- 頂点数: {', '.join(map(str, NODE_COUNTS))}",
        f"- WS近傍数: {', '.join(map(str, NEIGHBOR_COUNTS))}",
        "- WS再配線確率: "
        + ", ".join(map(str, REWIRING_PROBABILITIES)),
        f"- seed: {', '.join(map(str, SEEDS))}",
        "- 向き付け: 円環上の短い時計回り方向",
        "- 正解: 各グラフで k=1,...,|V| を厳密求解し、最小トーラス辺数を達成する最小kを採用",
        "",
        "## 正当性と速度",
        "",
        f"- 最小トーラス辺数一致: {torus_matches}/{len(rows)}",
        f"- それを達成する最小階層数も一致: {layer_matches}/{len(rows)}",
        f"- 提案手法の実行時間中央値: {statistics.median(row['proposed_seconds'] for row in rows):.4f} 秒",
        f"- 全探索の実行時間中央値: {statistics.median(row['exhaustive_seconds'] for row in rows):.4f} 秒",
        f"- 全探索に対する高速化率中央値: {statistics.median(speedups):.2f} 倍",
        "",
        "## 階層数設定との比較",
        "",
        "|方法|実行可能|実行不能|最適値を達成|非最適|余分なトーラス辺数の平均|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "fixed_3": "k=3",
        "fixed_5": "k=5",
        "existing": "k=ceil(sqrt(2|V|))",
        "proposed": "提案手法",
    }
    for summary in summaries:
        lines.append(
            f"|{labels[summary['method']]}|{summary['feasible']}|"
            f"{summary['infeasible']}|{summary['optimal']}|"
            f"{summary['suboptimal']}|{summary['mean_excess']:.3f}|"
        )
    lines.extend(
        [
            "",
            "余分なトーラス辺数の平均は、実行可能ケースを分母とし、最適ケースの0も含む。",
            "詳細は `raw_results.csv`、kごとの曲線は `torus_count_curves.csv`、比較集計は `summary.csv`。",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows, curve_rows, summaries


if __name__ == "__main__":
    run()
