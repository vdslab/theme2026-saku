"""提案トーラス描画パイプラインの段階別実行時間を測定する。"""

from __future__ import annotations

import csv
import statistics
import time
from pathlib import Path

from old_torus_layout.coordinate_assignment.brandes_koepf import (
    assign_torus_brandes_koepf_coordinates,
)
from old_torus_layout.crossing_reduction.radial import radial_sifting_global_guard_heuristic
from evaluate_layer_count_search import (
    NEIGHBOR_COUNTS,
    REWIRING_PROBABILITIES,
    SEEDS,
    generate_graph,
)
from old_torus_layout.layer_assignment.torus_balance import balance_layer_assignment
from old_torus_layout.layer_assignment.torus_binary_search import find_minimum_torus_configuration


BALANCE_METHOD = "diff_square"
CROSSING_ROUNDS = 5
NODE_COUNTS = tuple(range(10, 101, 10))
OUTPUT_DIR = Path("experiments/results/pipeline_runtime")
RAW_CSV = OUTPUT_DIR / "raw_results.csv"
SUMMARY_CSV = OUTPUT_DIR / "summary_by_nodes.csv"
REPORT_MD = OUTPUT_DIR / "PIPELINE_RUNTIME.md"


def measure_call(function, *args, **kwargs):
    """返り値と、呼び出し全体のwall-clock時間を返す。"""
    started = time.perf_counter()
    result = function(*args, **kwargs)
    return result, time.perf_counter() - started


def evaluate_case(nodes: int, neighbors: int, rewiring: float, seed: int):
    vertices, edges = generate_graph(nodes, neighbors, rewiring, seed)
    edges = sorted(set(edges))

    (layer_count, torus_count, _reported_step1), step1_seconds = measure_call(
        find_minimum_torus_configuration, vertices, edges
    )
    if layer_count is None:
        raise RuntimeError("layer assignment step 1 failed")

    (y_val, t_val, layer_dict, _reported_step2), step2_seconds = measure_call(
        balance_layer_assignment,
        vertices,
        edges,
        torus_count,
        layer_count,
        BALANCE_METHOD,
    )
    if not y_val:
        raise RuntimeError("layer assignment step 2 failed")

    (
        order,
        dummy_layers,
        dummy_edges,
        dummy_torus,
        psi,
    ), crossing_seconds = measure_call(
        radial_sifting_global_guard_heuristic,
        vertices,
        edges,
        layer_dict,
        t_val,
        rounds=CROSSING_ROUNDS,
    )

    positions, coordinate_seconds = measure_call(
        assign_torus_brandes_koepf_coordinates,
        order=order,
        layer_dict=dummy_layers,
        edges=dummy_edges,
        t_val=dummy_torus,
        psi=psi,
        original_nodes=vertices,
    )
    if len(positions) != sum(map(len, dummy_layers.values())):
        raise RuntimeError("coordinate assignment returned incomplete positions")

    total_seconds = (
        step1_seconds + step2_seconds + crossing_seconds + coordinate_seconds
    )
    return {
        "nodes": nodes,
        "neighbors": neighbors,
        "rewiring_probability": rewiring,
        "seed": seed,
        "edges": len(edges),
        "optimal_layer_count": layer_count,
        "torus_edges": torus_count,
        "dummy_nodes": sum(map(len, dummy_layers.values())) - len(vertices),
        "dummy_edges": len(dummy_edges),
        "step1_seconds": step1_seconds,
        "step2_seconds": step2_seconds,
        "crossing_seconds": crossing_seconds,
        "coordinate_seconds": coordinate_seconds,
        "total_seconds": total_seconds,
    }


def percentile(values, probability):
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def summarize_group(scope, rows):
    result = {"scope": scope, "graphs": len(rows)}
    for key in (
        "step1_seconds",
        "step2_seconds",
        "crossing_seconds",
        "coordinate_seconds",
        "total_seconds",
    ):
        values = [row[key] for row in rows]
        stem = key.removesuffix("_seconds")
        result[f"{stem}_median_seconds"] = statistics.median(values)
        result[f"{stem}_q1_seconds"] = percentile(values, 0.25)
        result[f"{stem}_q3_seconds"] = percentile(values, 0.75)
        result[f"{stem}_mean_seconds"] = statistics.mean(values)
    return result


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total_cases = (
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
                    row = evaluate_case(nodes, neighbors, rewiring, seed)
                    rows.append(row)
                    print(
                        f"[{case_number:>3}/{total_cases}] n={nodes:>2} "
                        f"k_ws={neighbors} p={rewiring:.1f} seed={seed} "
                        f"total={row['total_seconds']:.4f}s "
                        f"steps=({row['step1_seconds']:.4f}, "
                        f"{row['step2_seconds']:.4f}, "
                        f"{row['crossing_seconds']:.4f}, "
                        f"{row['coordinate_seconds']:.4f})",
                        flush=True,
                    )

    summaries = []
    for nodes in NODE_COUNTS:
        summaries.append(
            summarize_group(f"n={nodes}", [row for row in rows if row["nodes"] == nodes])
        )
    summaries.append(summarize_group("all", rows))
    write_csv(RAW_CSV, rows)
    write_csv(SUMMARY_CSV, summaries)

    overall = summaries[-1]
    phase_medians = {
        "階層割当1": overall["step1_median_seconds"],
        "階層割当2": overall["step2_median_seconds"],
        "交差削減": overall["crossing_median_seconds"],
        "座標割当": overall["coordinate_median_seconds"],
    }
    largest_phase = max(phase_medians, key=phase_medians.get)
    lines = [
        "# 提案パイプラインの段階別実行時間",
        "",
        "## 実験設計",
        "",
        f"- グラフ数: {len(rows)}",
        f"- 頂点数: {', '.join(map(str, NODE_COUNTS))}",
        f"- WS近傍数: {', '.join(map(str, NEIGHBOR_COUNTS))}",
        "- WS再配線確率: " + ", ".join(map(str, REWIRING_PROBABILITIES)),
        f"- seed: {', '.join(map(str, SEEDS))}",
        "- 向き付け: 円環上の短い時計回り方向",
        f"- 階層割当2: {BALANCE_METHOD}",
        f"- 交差削減: global-guard radial sifting、{CROSSING_ROUNDS} rounds",
        "- 計測: time.perf_counterによる各関数呼び出し全体のwall-clock時間",
        "- グラフ生成と最終描画の時間は含めない",
        "",
        f"## 全{len(rows)}件の中央値",
        "",
        f"- 階層割当1: {overall['step1_median_seconds']:.6f} 秒",
        f"- 階層割当2: {overall['step2_median_seconds']:.6f} 秒",
        f"- 交差削減: {overall['crossing_median_seconds']:.6f} 秒",
        f"- 座標割当: {overall['coordinate_median_seconds']:.6f} 秒",
        f"- 総合: {overall['total_median_seconds']:.6f} 秒",
        f"- 中央値が最大の段階: {largest_phase}",
        "",
        "## 頂点数別中央値",
        "",
        "|頂点数|階層割当1|階層割当2|交差削減|座標割当|総合|",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries[:-1]:
        lines.append(
            f"|{summary['scope'].removeprefix('n=')}|"
            f"{summary['step1_median_seconds']:.6f}|"
            f"{summary['step2_median_seconds']:.6f}|"
            f"{summary['crossing_median_seconds']:.6f}|"
            f"{summary['coordinate_median_seconds']:.6f}|"
            f"{summary['total_median_seconds']:.6f}|"
        )
    lines.extend(
        [
            "",
            "各頂点数には、近傍数2水準 × 再配線確率2水準 × 5 seed = 20件を含む。",
            "四分位範囲と平均は `summary_by_nodes.csv`、個別値は `raw_results.csv`。",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows, summaries


if __name__ == "__main__":
    run()
