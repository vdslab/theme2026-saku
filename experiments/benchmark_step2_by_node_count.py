"""同一条件でStep 2の実行時間とバランス指標をノード数別に集計する。"""

from __future__ import annotations

import csv
import statistics
import time
from pathlib import Path

from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration
from lib.generate_torus_graph import (
    generate_cyclic_graph,
    generate_dag,
    generate_mixed_graph,
    generate_random_connected_graph,
)


NODE_COUNTS = (8, 12, 20, 30, 50, 75, 100)
FAMILIES = ("dag", "mixed", "cyclic", "random")
SEEDS = (0, 1, 2)
DENSITY = 0.01
METHODS = ("diff", "diff_square", "qp", "barycenter")

OUTPUT_DIR = Path("experiments/results/step2_by_node_count")
LEGACY_RAW_CSV = OUTPUT_DIR / "raw_results.csv"
RAW_CSV = OUTPUT_DIR / "raw_results_wall.csv"
SUMMARY_CSV = OUTPUT_DIR / "summary.csv"
SUMMARY_MD = OUTPUT_DIR / "STEP2_BY_NODE_COUNT.md"

FIELDS = (
    "nodes",
    "family",
    "density",
    "seed",
    "edges",
    "layer_count",
    "torus_count",
    "method",
    "runtime_seconds",
    "wall_seconds",
    "span_sum",
    "span_square_sum",
    "span_imbalance_index",
    "layer_load_imbalance_index",
    "max_span",
    "same_layer_edges",
    "valid",
)


def generate_graph(family, nodes, seed):
    if family == "dag":
        return generate_dag(nodes, edge_prob=DENSITY, seed=seed)
    if family == "mixed":
        return generate_mixed_graph(
            nodes, edge_prob=DENSITY, cycle_prob=0.3, seed=seed
        )
    if family == "cyclic":
        return generate_cyclic_graph(
            nodes, num_cycles=2, edge_prob=DENSITY, seed=seed
        )
    if family == "random":
        return generate_random_connected_graph(
            nodes, edge_prob=DENSITY, seed=seed
        )
    raise ValueError(f"unknown family: {family}")


def edge_constraint_holds(y_u, y_v, is_torus, layer_count):
    t = int(bool(is_torus))
    return (
        y_u - y_v <= layer_count * t
        and y_u - y_v >= 1 - layer_count * (1 - t)
        and y_v - y_u >= 1 - layer_count * t
    )


def metrics(vertices, edges, layer_count, torus_count, layers, torus_edges):
    spans = [
        layers[v] - layers[u] + layer_count * int(torus_edges[(u, v)])
        for u, v in edges
    ]
    loads = [sum(layers[node] == layer for node in vertices) for layer in range(layer_count)]
    span_sum = sum(spans)
    span_square_sum = sum(span * span for span in spans)
    span_imbalance = len(spans) * span_square_sum / (span_sum * span_sum)
    layer_load_imbalance = layer_count * sum(load * load for load in loads) / (len(vertices) ** 2)
    valid = (
        sum(bool(torus_edges[edge]) for edge in edges) == torus_count
        and all(
            edge_constraint_holds(
                layers[u], layers[v], torus_edges[(u, v)], layer_count
            )
            for u, v in edges
        )
    )
    return {
        "span_sum": span_sum,
        "span_square_sum": span_square_sum,
        "span_imbalance_index": span_imbalance,
        "layer_load_imbalance_index": layer_load_imbalance,
        "max_span": max(spans),
        "same_layer_edges": sum(layers[u] == layers[v] for u, v in edges),
        "valid": valid,
    }


def load_existing():
    if not RAW_CSV.exists():
        return []
    with RAW_CSV.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def append_result(row):
    is_new = not RAW_CSV.exists()
    with RAW_CSV.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def benchmark():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_existing()
    completed = {
        (int(row["nodes"]), row["family"], int(row["seed"]), row["method"])
        for row in existing
    }
    case_params = {
        (int(row["nodes"]), row["family"], int(row["seed"])): (
            int(row["layer_count"]),
            int(row["torus_count"]),
        )
        for row in existing
    }
    if LEGACY_RAW_CSV.exists():
        with LEGACY_RAW_CSV.open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                case_params.setdefault(
                    (int(row["nodes"]), row["family"], int(row["seed"])),
                    (int(row["layer_count"]), int(row["torus_count"])),
                )

    for nodes in NODE_COUNTS:
        for family in FAMILIES:
            for seed in SEEDS:
                vertices, edges = generate_graph(family, nodes, seed)
                edges = sorted(set(edges))
                case_key = (nodes, family, seed)
                if all((*case_key, method) in completed for method in METHODS):
                    continue
                if case_key in case_params:
                    layer_count, torus_count = case_params[case_key]
                else:
                    layer_count, torus_count, _ = find_minimum_torus_configuration(
                        vertices, edges
                    )
                print(
                    f"case n={nodes} family={family} seed={seed} "
                    f"edges={len(edges)} L={layer_count} T={torus_count}",
                    flush=True,
                )
                for method in METHODS:
                    if (*case_key, method) in completed:
                        continue
                    started = time.perf_counter()
                    layers, torus_edges, _layer_dict, runtime = balance_layer_assignment(
                        vertices,
                        edges,
                        torus_count,
                        layer_count,
                        method,
                    )
                    wall_seconds = time.perf_counter() - started
                    result = {
                        "nodes": nodes,
                        "family": family,
                        "density": DENSITY,
                        "seed": seed,
                        "edges": len(edges),
                        "layer_count": layer_count,
                        "torus_count": torus_count,
                        "method": method,
                        "runtime_seconds": runtime,
                        "wall_seconds": wall_seconds,
                        **metrics(
                            vertices,
                            edges,
                            layer_count,
                            torus_count,
                            layers,
                            torus_edges,
                        ),
                    }
                    append_result(result)
                    print(
                        f"  {method}: solver={runtime:.4f}s wall={wall_seconds:.4f}s "
                        f"span-balance={result['span_imbalance_index']:.4f} "
                        f"load-balance={result['layer_load_imbalance_index']:.4f} "
                        f"valid={result['valid']}",
                        flush=True,
                    )


def aggregate():
    rows = load_existing()
    rows_by_case = {}
    for row in rows:
        case_key = (int(row["nodes"]), row["family"], int(row["seed"]))
        rows_by_case.setdefault(case_key, []).append(row)
    common_valid_cases = {
        case_key
        for case_key, case_rows in rows_by_case.items()
        if len(case_rows) == len(METHODS)
        and all(row["valid"] == "True" for row in case_rows)
    }

    grouped = {}
    for row in rows:
        case_key = (int(row["nodes"]), row["family"], int(row["seed"]))
        if case_key not in common_valid_cases:
            continue
        key = (int(row["nodes"]), row["method"])
        grouped.setdefault(key, []).append(row)

    summary_rows = []
    for nodes in NODE_COUNTS:
        for method in METHODS:
            group = grouped[(nodes, method)]
            summary_rows.append(
                {
                    "nodes": nodes,
                    "method": method,
                    "graphs": len(group),
                    "median_runtime_ms": 1000
                    * statistics.median(float(row["wall_seconds"]) for row in group),
                    "median_span_imbalance_index": statistics.median(
                        float(row["span_imbalance_index"]) for row in group
                    ),
                    "median_layer_load_imbalance_index": statistics.median(
                        float(row["layer_load_imbalance_index"]) for row in group
                    ),
                }
            )

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    lines = [
        "# Step 2：ノード数別の実行時間とバランス比較",
        "",
        "条件：密度0.01、DAG・Mixed・Cyclic・Random、各3 seed。各セルは最大12グラフの中央値。",
        "バランス指数は1.00が完全均等で、小さいほど良い。4手法すべてが有効な同一グラフだけで比較。",
        "",
        "| ノード数 | 手法 | 実行時間中央値 (ms) | エッジスパン不均衡指数 | レイヤー負荷不均衡指数 | 共通比較グラフ |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['nodes']} | {row['method']} | {row['median_runtime_ms']:.1f} "
            f"| {row['median_span_imbalance_index']:.3f} "
            f"| {row['median_layer_load_imbalance_index']:.3f} "
            f"| {row['graphs']}/12 |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    benchmark()
    aggregate()


if __name__ == "__main__":
    main()
