"""各ノードの入力・出力エッジ長が釣り合っているかを評価する。"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from benchmark_step2_by_node_count import (
    DENSITY,
    FAMILIES,
    METHODS,
    NODE_COUNTS,
    SEEDS,
    generate_graph,
)
from layer_assignment.torus_balance import balance_layer_assignment


TARGET_METHODS = ("diff", "diff_square", "barycenter")
OUTPUT_DIR = Path("experiments/results/node_front_back_balance")
PARAM_CSV = Path("experiments/results/step2_by_node_count/raw_results_wall.csv")
RAW_CSV = OUTPUT_DIR / "graph_method_balance.csv"
NODE_RAW_CSV = OUTPUT_DIR / "node_balance_raw.csv"
SUMMARY_CSV = OUTPUT_DIR / "summary_by_node_count.csv"
REPORT_MD = OUTPUT_DIR / "NODE_FRONT_BACK_BALANCE.md"

RAW_FIELDS = (
    "nodes",
    "family",
    "density",
    "seed",
    "edges",
    "layer_count",
    "torus_count",
    "method",
    "eligible_nodes",
    "excluded_source_or_sink_nodes",
    "mean_node_imbalance",
    "median_node_imbalance",
    "p90_node_imbalance",
    "balanced_within_10pct_ratio",
    "balanced_within_20pct_ratio",
    "node_imbalances_json",
)


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def node_balance_metrics(vertices, edges, layer_count, layers, torus_edges):
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for u, v in edges:
        span = layers[v] - layers[u] + layer_count * int(torus_edges[(u, v)])
        outgoing[u].append(span)
        incoming[v].append(span)

    node_values = {}
    for node in vertices:
        if not incoming[node] or not outgoing[node]:
            continue
        mean_in = statistics.mean(incoming[node])
        mean_out = statistics.mean(outgoing[node])
        imbalance = abs(mean_in - mean_out) / (mean_in + mean_out)
        node_values[node] = {
            "mean_in_span": mean_in,
            "mean_out_span": mean_out,
            "imbalance": imbalance,
            "in_degree": len(incoming[node]),
            "out_degree": len(outgoing[node]),
        }

    values = [value["imbalance"] for value in node_values.values()]
    return {
        "eligible_nodes": len(values),
        "excluded_source_or_sink_nodes": len(vertices) - len(values),
        "mean_node_imbalance": statistics.mean(values),
        "median_node_imbalance": statistics.median(values),
        "p90_node_imbalance": percentile(values, 0.9),
        "balanced_within_10pct_ratio": sum(value <= 0.1 for value in values) / len(values),
        "balanced_within_20pct_ratio": sum(value <= 0.2 for value in values) / len(values),
        "node_imbalances_json": json.dumps(node_values, separators=(",", ":")),
    }


def load_params():
    params = {}
    with PARAM_CSV.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            params[(int(row["nodes"]), row["family"], int(row["seed"]))] = (
                int(row["layer_count"]),
                int(row["torus_count"]),
            )
    return params


def load_raw():
    if not RAW_CSV.exists():
        return []
    with RAW_CSV.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def append_raw(row):
    is_new = not RAW_CSV.exists()
    with RAW_CSV.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=RAW_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def evaluate():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    params = load_params()
    existing = load_raw()
    completed = {
        (int(row["nodes"]), row["family"], int(row["seed"]), row["method"])
        for row in existing
    }

    for nodes in NODE_COUNTS:
        for family in FAMILIES:
            for seed in SEEDS:
                vertices, edges = generate_graph(family, nodes, seed)
                edges = sorted(set(edges))
                layer_count, torus_count = params[(nodes, family, seed)]
                for method in TARGET_METHODS:
                    key = (nodes, family, seed, method)
                    if key in completed:
                        continue
                    layers, torus_edges, _layer_dict, _runtime = balance_layer_assignment(
                        vertices,
                        edges,
                        torus_count,
                        layer_count,
                        method,
                    )
                    result = {
                        "nodes": nodes,
                        "family": family,
                        "density": DENSITY,
                        "seed": seed,
                        "edges": len(edges),
                        "layer_count": layer_count,
                        "torus_count": torus_count,
                        "method": method,
                        **node_balance_metrics(
                            vertices,
                            edges,
                            layer_count,
                            layers,
                            torus_edges,
                        ),
                    }
                    append_raw(result)
                    print(
                        f"n={nodes} {family} seed={seed} {method}: "
                        f"mean={result['mean_node_imbalance']:.4f} "
                        f"median={result['median_node_imbalance']:.4f} "
                        f"eligible={result['eligible_nodes']}",
                        flush=True,
                    )


def summarize():
    rows = load_raw()
    grouped = defaultdict(list)
    pooled_nodes = defaultdict(list)
    for row in rows:
        grouped[(int(row["nodes"]), row["method"])].append(row)
        node_values = json.loads(row["node_imbalances_json"])
        pooled_nodes[(int(row["nodes"]), row["method"])].extend(
            value["imbalance"] for value in node_values.values()
        )

    summary_rows = []
    for nodes in NODE_COUNTS:
        for method in TARGET_METHODS:
            group = grouped[(nodes, method)]
            values = pooled_nodes[(nodes, method)]
            summary_rows.append(
                {
                    "nodes": nodes,
                    "method": method,
                    "graphs": len(group),
                    "eligible_nodes": len(values),
                    "median_of_graph_mean_imbalance": statistics.median(
                        float(row["mean_node_imbalance"]) for row in group
                    ),
                    "pooled_node_median_imbalance": statistics.median(values),
                    "pooled_node_p90_imbalance": percentile(values, 0.9),
                    "pooled_balanced_within_10pct_ratio": sum(v <= 0.1 for v in values)
                    / len(values),
                    "pooled_balanced_within_20pct_ratio": sum(v <= 0.2 for v in values)
                    / len(values),
                }
            )

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    with NODE_RAW_CSV.open("w", newline="", encoding="utf-8") as output:
        fields = (
            "nodes",
            "family",
            "seed",
            "method",
            "node",
            "mean_in_span",
            "mean_out_span",
            "imbalance",
            "in_degree",
            "out_degree",
        )
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            for node, value in json.loads(row["node_imbalances_json"]).items():
                writer.writerow(
                    {
                        "nodes": row["nodes"],
                        "family": row["family"],
                        "seed": row["seed"],
                        "method": row["method"],
                        "node": node,
                        **value,
                    }
                )

    lines = [
        "# ノード前後のエッジ長バランス評価",
        "",
        "各ノードについて、入力エッジの平均スパンと出力エッジの平均スパンを比較する。",
        "",
        "`imbalance = |mean_in - mean_out| / (mean_in + mean_out)`",
        "",
        "0が完全に釣り合い、1に近いほど前後の偏りが大きい。入力または出力を持たないノードは除外する。",
        "",
        "| ノード数 | 手法 | グラフ平均不均衡・中央値 | 全対象ノード中央値 | 全対象ノード90%点 | 10%以内のノード | 20%以内のノード | 対象ノード |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['nodes']} | {row['method']} "
            f"| {row['median_of_graph_mean_imbalance']:.3f} "
            f"| {row['pooled_node_median_imbalance']:.3f} "
            f"| {row['pooled_node_p90_imbalance']:.3f} "
            f"| {100 * row['pooled_balanced_within_10pct_ratio']:.1f}% "
            f"| {100 * row['pooled_balanced_within_20pct_ratio']:.1f}% "
            f"| {row['eligible_nodes']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    evaluate()
    summarize()


if __name__ == "__main__":
    main()
