"""トーラス統合処理と座標割当のアブレーション実験。"""

from __future__ import annotations

import csv
import math
import statistics
import time
from pathlib import Path

from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates
from crossing_reduction import radial
from drawing.draw_radial_torus import draw_radial_torus
from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration
from lib.insert_dummy_node import insert_dummy_node

from evaluate_layer_count_search import FAMILIES, NODE_COUNTS, SEEDS, generate_graph


ROUNDS = 5
OUTPUT_DIR = Path("experiments/results/torus_framework_ablation")
RAW_CSV = OUTPUT_DIR / "crossing_ablation_raw.csv"
COORDINATE_CSV = OUTPUT_DIR / "coordinate_ablation_raw.csv"
SUMMARY_MD = OUTPUT_DIR / "TORUS_FRAMEWORK_ABLATION.md"

CROSSING_VARIANTS = (
    "order_only",
    "joint_psi",
    "joint_psi_rotation",
    "full_guard_rotation",
)
COORDINATE_VARIANTS = ("uniform", "bk_no_smoothing", "bk_torus_smoothing")


def prepare_embedding(vertices, edges, layer_dict, torus_edges):
    original_nodes = set(vertices)
    dummy_vertices, dummy_edges, dummy_layers, dummy_torus, _weights = (
        insert_dummy_node(vertices, edges, layer_dict, torus_edges)
    )
    layers = sorted(dummy_layers)
    dummy_nodes = set(dummy_vertices) - original_nodes
    initial_order = radial._initial_orders(dummy_layers, layers, dummy_edges)[0]
    initial_psi = radial._compute_winding_numbers(
        dummy_edges, initial_order, dummy_layers, layers
    )
    return (
        dummy_vertices,
        dummy_edges,
        dummy_layers,
        dummy_torus,
        layers,
        dummy_nodes,
        initial_order,
        initial_psi,
    )


def run_crossing_variant(prepared, variant):
    (
        _dummy_vertices,
        dummy_edges,
        dummy_layers,
        _dummy_torus,
        layers,
        dummy_nodes,
        initial_order,
        initial_psi,
    ) = prepared
    order = radial._copy_order(initial_order)
    psi = dict(initial_psi)
    started = time.perf_counter()

    if variant == "order_only":
        radial._run_sifting(
            order,
            psi,
            layers,
            dummy_edges,
            rounds=ROUNDS,
            dummy_nodes=dummy_nodes,
            optimize_winding=False,
        )
    elif variant == "joint_psi":
        radial._run_sifting(
            order,
            psi,
            layers,
            dummy_edges,
            rounds=ROUNDS,
            dummy_nodes=dummy_nodes,
        )
    elif variant == "joint_psi_rotation":
        radial._run_sifting(
            order,
            psi,
            layers,
            dummy_edges,
            rounds=ROUNDS,
            dummy_nodes=dummy_nodes,
        )
        radial._postprocess_sifting_rotations(order, psi, layers, dummy_edges)
    elif variant == "full_guard_rotation":
        radial._run_sifting_with_global_guard(
            order,
            psi,
            layers,
            dummy_edges,
            rounds=ROUNDS,
            dummy_nodes=dummy_nodes,
        )
        guarded_order = radial._copy_order(order)
        guarded_psi = dict(psi)
        guarded_crossings = radial._count_all_crossings(
            order, psi, layers, dummy_edges
        )
        radial._postprocess_sifting_rotations(order, psi, layers, dummy_edges)
        if radial._count_all_crossings(order, psi, layers, dummy_edges) > guarded_crossings:
            order = guarded_order
            psi = guarded_psi
    else:
        raise ValueError(f"unknown crossing variant: {variant}")

    runtime = time.perf_counter() - started
    crossings = radial.count_radial_crossings(
        order, psi, dummy_layers, dummy_edges
    )
    return order, psi, crossings, runtime


def uniform_coordinates(order, layers):
    return {
        node: (float(layer_index), float(node_index))
        for layer_index, layer in enumerate(layers)
        for node_index, node in enumerate(order[layer])
    }


def geometry_metrics(order, layers, edges, torus_edges, psi, positions):
    horizontal_period = len(layers)
    vertical_period = max(len(order[layer]) for layer in layers)
    lengths = []
    angles = []
    for edge in edges:
        u, v = edge
        dx = positions[v][0] - positions[u][0]
        dy = positions[v][1] - positions[u][1]
        if torus_edges.get(edge, False):
            dx += horizontal_period
        dy += vertical_period * psi.get(edge, 0)
        lengths.append(math.hypot(dx, dy))
        angles.append(math.degrees(math.atan2(abs(dy), abs(dx))))

    sorted_angles = sorted(angles)
    p95_index = min(len(sorted_angles) - 1, math.ceil(0.95 * len(sorted_angles)) - 1)
    return {
        "mean_edge_length": statistics.mean(lengths),
        "max_edge_length": max(lengths),
        "mean_abs_angle_degrees": statistics.mean(angles),
        "p95_abs_angle_degrees": sorted_angles[p95_index],
        "vertical_boundary_passes": sum(abs(value) for value in psi.values()),
        "horizontal_boundary_passes": sum(
            bool(torus_edges.get(edge, False)) for edge in edges
        ),
    }


def coordinate_variant(
    variant,
    vertices,
    order,
    layers,
    dummy_layers,
    dummy_edges,
    dummy_torus,
    psi,
):
    started = time.perf_counter()
    if variant == "uniform":
        positions = uniform_coordinates(order, layers)
    elif variant == "bk_no_smoothing":
        positions = assign_torus_brandes_koepf_coordinates(
            order,
            dummy_layers,
            dummy_edges,
            t_val=dummy_torus,
            psi=psi,
            smooth_iterations=0,
            original_nodes=vertices,
        )
    elif variant == "bk_torus_smoothing":
        positions = assign_torus_brandes_koepf_coordinates(
            order,
            dummy_layers,
            dummy_edges,
            t_val=dummy_torus,
            psi=psi,
            original_nodes=vertices,
        )
    else:
        raise ValueError(f"unknown coordinate variant: {variant}")
    runtime = time.perf_counter() - started
    metrics = geometry_metrics(
        order, layers, dummy_edges, dummy_torus, psi, positions
    )
    return positions, runtime, metrics


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def aggregate(crossing_rows, coordinate_rows):
    case_count = len(crossing_rows) // len(CROSSING_VARIANTS)
    crossing_by_case = {}
    for row in crossing_rows:
        key = (row["nodes"], row["family"], row["seed"])
        crossing_by_case.setdefault(key, {})[row["variant"]] = row

    crossing_summary = []
    for variant in CROSSING_VARIANTS:
        rows = [row for row in crossing_rows if row["variant"] == variant]
        reductions = []
        comparisons = []
        for case in crossing_by_case.values():
            baseline = case["order_only"]["crossings"]
            result = case[variant]["crossings"]
            comparisons.append((result > baseline) - (result < baseline))
            if baseline:
                reductions.append((baseline - result) / baseline)
        crossing_summary.append(
            {
                "variant": variant,
                "crossings": statistics.median(row["crossings"] for row in rows),
                "reduction": 100 * statistics.mean(reductions) if reductions else 0,
                "vertical": statistics.median(
                    row["vertical_boundary_passes"] for row in rows
                ),
                "runtime": 1000
                * statistics.median(row["runtime_seconds"] for row in rows),
                "improved": sum(value < 0 for value in comparisons),
                "equal": sum(value == 0 for value in comparisons),
                "worsened": sum(value > 0 for value in comparisons),
            }
        )

    baseline_total = sum(
        case["order_only"]["crossings"] for case in crossing_by_case.values()
    )
    full_total = sum(
        case["full_guard_rotation"]["crossings"]
        for case in crossing_by_case.values()
    )
    total_reduction = 100 * (baseline_total - full_total) / baseline_total

    coordinate_summary = []
    for variant in COORDINATE_VARIANTS:
        rows = [row for row in coordinate_rows if row["variant"] == variant]
        coordinate_summary.append(
            {
                "variant": variant,
                "length": statistics.median(row["mean_edge_length"] for row in rows),
                "angle": statistics.median(
                    row["mean_abs_angle_degrees"] for row in rows
                ),
                "p95": statistics.median(
                    row["p95_abs_angle_degrees"] for row in rows
                ),
                "runtime": 1000
                * statistics.median(row["runtime_seconds"] for row in rows),
            }
        )

    labels = {
        "order_only": "順序のみ（ψ固定）",
        "joint_psi": "順序＋ψ同時調整",
        "joint_psi_rotation": "順序＋ψ＋回転補正",
        "full_guard_rotation": "全処理（Global Guard付き）",
        "uniform": "等間隔座標",
        "bk_no_smoothing": "BK座標割当",
        "bk_torus_smoothing": "BK＋トーラス平滑化",
    }
    lines = [
        "# トーラス描画フレームワークのアブレーション実験",
        "",
        f"同じ階層割当を用いた{case_count}グラフで比較。Radial Siftingは{ROUNDS} rounds。",
        "",
        "## 交差削減統合処理",
        "",
        "|条件|交差数中央値|順序のみからの平均削減率|改善・同率・悪化|上下境界通過数中央値|時間中央値(ms)|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in crossing_summary:
        lines.append(
            f"|{labels[row['variant']]}|{row['crossings']:.1f}|{row['reduction']:.2f}%|"
            f"{row['improved']}・{row['equal']}・{row['worsened']}|"
            f"{row['vertical']:.1f}|{row['runtime']:.2f}|"
        )
    lines.extend(
        [
            "",
            f"全処理版の総交差数は{baseline_total:,}から{full_total:,}へ減少した（{total_reduction:.2f}%削減）。",
            "",
            "## 座標割当",
            "",
            "|条件|平均辺長の中央値|平均絶対傾斜角|95%傾斜角|時間中央値(ms)|",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in coordinate_summary:
        lines.append(
            f"|{labels[row['variant']]}|{row['length']:.3f}|{row['angle']:.2f}°|"
            f"{row['p95']:.2f}°|{row['runtime']:.3f}|"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    crossing_rows = []
    coordinate_rows = []

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
                prepared = prepare_embedding(vertices, edges, layer_dict, t_val)
                (
                    _dummy_vertices,
                    dummy_edges,
                    dummy_layers,
                    dummy_torus,
                    layers,
                    _dummy_nodes,
                    _initial_order,
                    _initial_psi,
                ) = prepared

                variant_results = {}
                for variant in CROSSING_VARIANTS:
                    order, psi, crossings, runtime = run_crossing_variant(
                        prepared, variant
                    )
                    variant_results[variant] = (order, psi)
                    crossing_rows.append(
                        {
                            "nodes": nodes,
                            "family": family,
                            "seed": seed,
                            "edges": len(edges),
                            "dummy_edges": len(dummy_edges),
                            "layer_count": layer_count,
                            "torus_count": torus_count,
                            "variant": variant,
                            "crossings": crossings,
                            "vertical_boundary_passes": sum(
                                abs(value) for value in psi.values()
                            ),
                            "horizontal_boundary_passes": sum(dummy_torus.values()),
                            "runtime_seconds": runtime,
                        }
                    )

                full_order, full_psi = variant_results["full_guard_rotation"]
                for variant in COORDINATE_VARIANTS:
                    _positions, runtime, metrics = coordinate_variant(
                        variant,
                        vertices,
                        full_order,
                        layers,
                        dummy_layers,
                        dummy_edges,
                        dummy_torus,
                        full_psi,
                    )
                    coordinate_rows.append(
                        {
                            "nodes": nodes,
                            "family": family,
                            "seed": seed,
                            "edges": len(edges),
                            "dummy_edges": len(dummy_edges),
                            "layer_count": layer_count,
                            "variant": variant,
                            **metrics,
                            "runtime_seconds": runtime,
                        }
                    )
                print(
                    f"n={nodes:>2} {family:<6} seed={seed} "
                    + " ".join(
                        f"{variant}={next(row['crossings'] for row in reversed(crossing_rows) if row['variant'] == variant)}"
                        for variant in CROSSING_VARIANTS
                    ),
                    flush=True,
                )

    write_rows(RAW_CSV, crossing_rows)
    write_rows(COORDINATE_CSV, coordinate_rows)
    aggregate(crossing_rows, coordinate_rows)


if __name__ == "__main__":
    run()
