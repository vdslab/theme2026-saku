"""有向3ノード列 u->v->w の前後エッジスパンを比較する。"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from benchmark_step2_by_node_count import DENSITY, FAMILIES, NODE_COUNTS, SEEDS, generate_graph
from layer_assignment.torus_balance import balance_layer_assignment


METHODS = ("diff", "diff_square", "barycenter")
OUTPUT_DIR = Path("experiments/results/three_node_path_balance")
PARAM_CSV = Path("experiments/results/step2_by_node_count/raw_results_wall.csv")
RAW_CSV = OUTPUT_DIR / "graph_method_path_balance.csv"
PATH_RAW_CSV = OUTPUT_DIR / "path_balance_raw.csv"
SUMMARY_CSV = OUTPUT_DIR / "summary_by_node_count.csv"
REPORT_MD = OUTPUT_DIR / "THREE_NODE_PATH_BALANCE.md"

RAW_FIELDS = (
    "nodes",
    "family",
    "density",
    "seed",
    "edges",
    "layer_count",
    "torus_count",
    "method",
    "path_count",
    "middle_node_count",
    "mean_path_imbalance",
    "median_path_imbalance",
    "p90_path_imbalance",
    "balanced_within_10pct_ratio",
    "balanced_within_20pct_ratio",
    "paths_json",
)


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def path_balance_metrics(vertices, edges, layer_count, layers, torus_edges):
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for u, v in edges:
        span = layers[v] - layers[u] + layer_count * int(torus_edges[(u, v)])
        outgoing[u].append((v, span))
        incoming[v].append((u, span))

    paths = []
    middle_nodes = set()
    for v in vertices:
        for u, incoming_span in incoming[v]:
            for w, outgoing_span in outgoing[v]:
                if u == w:
                    continue
                imbalance = abs(incoming_span - outgoing_span) / (
                    incoming_span + outgoing_span
                )
                paths.append(
                    {
                        "u": u,
                        "v": v,
                        "w": w,
                        "incoming_span": incoming_span,
                        "outgoing_span": outgoing_span,
                        "imbalance": imbalance,
                    }
                )
                middle_nodes.add(v)

    values = [path["imbalance"] for path in paths]
    return {
        "path_count": len(paths),
        "middle_node_count": len(middle_nodes),
        "mean_path_imbalance": statistics.mean(values),
        "median_path_imbalance": statistics.median(values),
        "p90_path_imbalance": percentile(values, 0.9),
        "balanced_within_10pct_ratio": sum(value <= 0.1 for value in values) / len(values),
        "balanced_within_20pct_ratio": sum(value <= 0.2 for value in values) / len(values),
        "paths_json": json.dumps(paths, separators=(",", ":")),
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
    completed = {
        (int(row["nodes"]), row["family"], int(row["seed"]), row["method"])
        for row in load_raw()
    }

    for nodes in NODE_COUNTS:
        for family in FAMILIES:
            for seed in SEEDS:
                vertices, edges = generate_graph(family, nodes, seed)
                edges = sorted(set(edges))
                layer_count, torus_count = params[(nodes, family, seed)]
                for method in METHODS:
                    key = (nodes, family, seed, method)
                    if key in completed:
                        continue
                    layers, torus_edges, _layer_dict, _runtime = balance_layer_assignment(
                        vertices, edges, torus_count, layer_count, method
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
                        **path_balance_metrics(
                            vertices, edges, layer_count, layers, torus_edges
                        ),
                    }
                    append_raw(result)
                    print(
                        f"n={nodes} {family} seed={seed} {method}: "
                        f"mean={result['mean_path_imbalance']:.4f} "
                        f"paths={result['path_count']}",
                        flush=True,
                    )


def summarize():
    rows = load_raw()
    grouped = defaultdict(list)
    pooled_paths = defaultdict(list)
    by_case = defaultdict(dict)
    for row in rows:
        nodes = int(row["nodes"])
        grouped[(nodes, row["method"])].append(row)
        path_values = [path["imbalance"] for path in json.loads(row["paths_json"])]
        pooled_paths[(nodes, row["method"])].extend(path_values)
        by_case[(nodes, row["family"], int(row["seed"]))][row["method"]] = row

    best_tied = {
        method: sum(
            float(case[method]["mean_path_imbalance"])
            <= min(float(case[candidate]["mean_path_imbalance"]) for candidate in METHODS)
            + 1e-12
            for case in by_case.values()
        )
        for method in METHODS
    }

    summary_rows = []
    for nodes in NODE_COUNTS:
        for method in METHODS:
            group = grouped[(nodes, method)]
            values = pooled_paths[(nodes, method)]
            summary_rows.append(
                {
                    "nodes": nodes,
                    "method": method,
                    "graphs": len(group),
                    "paths": len(values),
                    "median_of_graph_mean_path_imbalance": statistics.median(
                        float(row["mean_path_imbalance"]) for row in group
                    ),
                    "pooled_path_median_imbalance": statistics.median(values),
                    "pooled_path_p90_imbalance": percentile(values, 0.9),
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

    with PATH_RAW_CSV.open("w", newline="", encoding="utf-8") as output:
        fields = (
            "nodes",
            "family",
            "seed",
            "method",
            "u",
            "v",
            "w",
            "incoming_span",
            "outgoing_span",
            "imbalance",
        )
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            for path in json.loads(row["paths_json"]):
                writer.writerow(
                    {
                        "nodes": row["nodes"],
                        "family": row["family"],
                        "seed": row["seed"],
                        "method": row["method"],
                        **path,
                    }
                )

    all_pooled = defaultdict(list)
    for row in rows:
        all_pooled[row["method"]].extend(
            path["imbalance"] for path in json.loads(row["paths_json"])
        )

    lines = [
        "# 3ノードパスの前後エッジバランス評価",
        "",
        "有向3ノード列 `u -> v -> w` ごとに、2本のエッジスパンを比較する。`u == w` の2サイクルは除外する。",
        "",
        "`imbalance = |span(u,v) - span(v,w)| / (span(u,v) + span(v,w))`",
        "",
        "0が完全に釣り合い、1に近いほど前後エッジの長さが異なる。",
        "",
        "## 全体結果",
        "",
        "| 手法 | 全パス平均 | 全パス中央値 | 全パス90%点 | 10%以内 | 20%以内 | グラフ平均が最良・同率 | パス数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        values = all_pooled[method]
        lines.append(
            f"| {method} | {statistics.mean(values):.3f} "
            f"| {statistics.median(values):.3f} "
            f"| {percentile(values, 0.9):.3f} "
            f"| {100 * sum(v <= 0.1 for v in values) / len(values):.1f}% "
            f"| {100 * sum(v <= 0.2 for v in values) / len(values):.1f}% "
            f"| {best_tied[method]}/84 | {len(values)} |"
        )
    lines.extend(
        [
            "",
            "## ノード数別結果",
            "",
            "各セルは12グラフについて計算したパス平均不均衡の中央値。小さいほど良い。",
            "",
            "| ノード数 | diff | diff_square | barycenter |",
            "|---:|---:|---:|---:|",
        ]
    )
    for nodes in NODE_COUNTS:
        values = {
            row["method"]: row["median_of_graph_mean_path_imbalance"]
            for row in summary_rows
            if row["nodes"] == nodes
        }
        minimum = min(values.values())
        formatted = {
            method: (
                f"**{values[method]:.3f}**"
                if abs(values[method] - minimum) < 1e-12
                else f"{values[method]:.3f}"
            )
            for method in METHODS
        }
        lines.append(
            f"| {nodes} | {formatted['diff']} | {formatted['diff_square']} "
            f"| {formatted['barycenter']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    evaluate()
    summarize()


if __name__ == "__main__":
    main()
