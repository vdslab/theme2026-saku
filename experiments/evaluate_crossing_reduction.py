"""同一の階層割当に対してトーラス交差削減手法を比較する実験。"""

from __future__ import annotations

import csv
import statistics
import time
from pathlib import Path

from crossing_reduction.radial import (
    cartesian_barycenter_heuristic,
    count_radial_crossings,
    radial_sifting_global_guard_heuristic,
    radial_sifting_heuristic,
)
from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration
from evaluate_layer_count_search import FAMILIES, NODE_COUNTS, SEEDS, generate_graph


ROUNDS = 5
METHODS = {
    "barycenter_initial": lambda v, a, layers, torus: cartesian_barycenter_heuristic(
        v, a, layers, torus
    ),
    "radial_sifting": lambda v, a, layers, torus: radial_sifting_heuristic(
        v, a, layers, torus, rounds=ROUNDS
    ),
    "radial_sifting_guard": lambda v, a, layers, torus: (
        radial_sifting_global_guard_heuristic(
            v, a, layers, torus, rounds=ROUNDS
        )
    ),
}

OUTPUT_DIR = Path("experiments/results/crossing_reduction")
RAW_CSV = OUTPUT_DIR / "raw_results.csv"
SUMMARY_MD = OUTPUT_DIR / "CROSSING_REDUCTION.md"


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    for nodes in NODE_COUNTS:
        for family in FAMILIES:
            for seed in SEEDS:
                vertices, edges = generate_graph(family, nodes, seed)
                edges = sorted(set(edges))
                layer_count, torus_count, _ = find_minimum_torus_configuration(
                    vertices, edges
                )
                y_val, t_val, layer_dict, _ = balance_layer_assignment(
                    vertices, edges, torus_count, layer_count, "diff_square"
                )
                if not y_val:
                    raise RuntimeError(
                        f"layer assignment failed: n={nodes} {family} seed={seed}"
                    )

                case_results = {}
                for method, implementation in METHODS.items():
                    started = time.perf_counter()
                    order, dummy_layers, dummy_edges, dummy_torus, psi = implementation(
                        vertices, edges, layer_dict, t_val
                    )
                    runtime = time.perf_counter() - started
                    crossings = count_radial_crossings(
                        order, psi, dummy_layers, dummy_edges
                    )
                    case_results[method] = crossings
                    rows.append(
                        {
                            "nodes": nodes,
                            "family": family,
                            "seed": seed,
                            "edges": len(edges),
                            "layer_count": layer_count,
                            "torus_count": torus_count,
                            "method": method,
                            "rounds": 0 if method == "barycenter_initial" else ROUNDS,
                            "crossings": crossings,
                            "runtime_seconds": runtime,
                            "dummy_nodes": sum(len(v) for v in dummy_layers.values())
                            - len(vertices),
                            "winding_edges": sum(value != 0 for value in psi.values()),
                        }
                    )
                print(
                    f"n={nodes:>2} {family:<6} seed={seed} E={len(edges):>3} "
                    f"crossings={case_results}",
                    flush=True,
                )

    with RAW_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    by_case = {}
    for row in rows:
        key = (row["nodes"], row["family"], row["seed"])
        by_case.setdefault(key, {})[row["method"]] = row

    summary = []
    for method in METHODS:
        method_rows = [row for row in rows if row["method"] == method]
        comparisons = []
        reductions = []
        for case in by_case.values():
            initial = case["barycenter_initial"]["crossings"]
            result = case[method]["crossings"]
            comparisons.append((result > initial) - (result < initial))
            if initial > 0:
                reductions.append((initial - result) / initial)
        summary.append(
            {
                "method": method,
                "median_crossings": statistics.median(
                    row["crossings"] for row in method_rows
                ),
                "mean_reduction_percent": 100 * statistics.mean(reductions)
                if reductions
                else 0.0,
                "improved": sum(value < 0 for value in comparisons),
                "equal": sum(value == 0 for value in comparisons),
                "worsened": sum(value > 0 for value in comparisons),
                "median_runtime_ms": 1000
                * statistics.median(row["runtime_seconds"] for row in method_rows),
            }
        )

    initial_total = sum(
        case["barycenter_initial"]["crossings"] for case in by_case.values()
    )
    guard_total = sum(
        case["radial_sifting_guard"]["crossings"] for case in by_case.values()
    )
    total_reduction = (
        100 * (initial_total - guard_total) / initial_total if initial_total else 0.0
    )

    lines = [
        "# トーラス交差削減の比較",
        "",
        f"共通の `diff_square` 階層割当を用いた {len(by_case)} グラフで比較。Siftingは{ROUNDS} rounds。",
        "交差削減率は初期配置の交差数が0でないケースだけで計算。",
        f"全交差数は {initial_total} から {guard_total} に減少（{total_reduction:.2f}%削減）。",
        "",
        "|手法|交差数中央値|平均削減率|改善|同率|悪化|時間中央値(ms)|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"|{row['method']}|{row['median_crossings']:.1f}|"
            f"{row['mean_reduction_percent']:.2f}%|{row['improved']}|"
            f"{row['equal']}|{row['worsened']}|{row['median_runtime_ms']:.3f}|"
        )
    lines.extend(["", "詳細は `raw_results.csv`。"])
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
