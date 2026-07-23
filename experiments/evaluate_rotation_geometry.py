"""回転補正の前後で境界通過数と最終座標の幾何品質を比較する。"""

from __future__ import annotations

import csv
import statistics
import time

from coordinate_assignment.brandes_koepf import assign_torus_brandes_koepf_coordinates
from crossing_reduction import radial
from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration

from evaluate_layer_count_search import FAMILIES, NODE_COUNTS, SEEDS, generate_graph
from evaluate_torus_framework_ablation import (
    OUTPUT_DIR,
    geometry_metrics,
    prepare_embedding,
)


RAW_CSV = OUTPUT_DIR / "rotation_geometry_raw.csv"
SUMMARY_MD = OUTPUT_DIR / "ROTATION_GEOMETRY.md"
ROUNDS = 5


def run():
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
                prepared = prepare_embedding(vertices, edges, layer_dict, t_val)
                (
                    _dummy_vertices,
                    dummy_edges,
                    dummy_layers,
                    dummy_torus,
                    layers,
                    dummy_nodes,
                    initial_order,
                    initial_psi,
                ) = prepared
                order = radial._copy_order(initial_order)
                psi = dict(initial_psi)
                radial._run_sifting_with_global_guard(
                    order,
                    psi,
                    layers,
                    dummy_edges,
                    rounds=ROUNDS,
                    dummy_nodes=dummy_nodes,
                )

                for variant in ("before_rotation", "after_rotation"):
                    started = time.perf_counter()
                    if variant == "after_rotation":
                        radial._postprocess_sifting_rotations(
                            order, psi, layers, dummy_edges
                        )
                    rotation_seconds = time.perf_counter() - started
                    coordinate_started = time.perf_counter()
                    positions = assign_torus_brandes_koepf_coordinates(
                        order,
                        dummy_layers,
                        dummy_edges,
                        t_val=dummy_torus,
                        psi=psi,
                        original_nodes=vertices,
                    )
                    coordinate_seconds = time.perf_counter() - coordinate_started
                    metrics = geometry_metrics(
                        order,
                        layers,
                        dummy_edges,
                        dummy_torus,
                        psi,
                        positions,
                    )
                    rows.append(
                        {
                            "nodes": nodes,
                            "family": family,
                            "seed": seed,
                            "variant": variant,
                            "crossings": radial.count_radial_crossings(
                                order, psi, dummy_layers, dummy_edges
                            ),
                            **metrics,
                            "rotation_seconds": rotation_seconds,
                            "coordinate_seconds": coordinate_seconds,
                        }
                    )
                print(f"n={nodes:>2} {family:<6} seed={seed}", flush=True)

    with RAW_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    by_case = {}
    for row in rows:
        key = (row["nodes"], row["family"], row["seed"])
        by_case.setdefault(key, {})[row["variant"]] = row
    changes = {}
    for metric in (
        "vertical_boundary_passes",
        "mean_edge_length",
        "mean_abs_angle_degrees",
        "p95_abs_angle_degrees",
    ):
        differences = [
            case["after_rotation"][metric] - case["before_rotation"][metric]
            for case in by_case.values()
        ]
        changes[metric] = {
            "before": statistics.median(
                case["before_rotation"][metric] for case in by_case.values()
            ),
            "after": statistics.median(
                case["after_rotation"][metric] for case in by_case.values()
            ),
            "improved": sum(value < -1e-9 for value in differences),
            "equal": sum(abs(value) < 1e-9 for value in differences),
            "worsened": sum(value > 1e-9 for value in differences),
        }

    labels = {
        "vertical_boundary_passes": "上下境界通過数",
        "mean_edge_length": "平均辺長",
        "mean_abs_angle_degrees": "平均絶対傾斜角",
        "p95_abs_angle_degrees": "95%傾斜角",
    }
    lines = [
        "# 回転補正の幾何品質比較",
        "",
        "|指標|補正前中央値|補正後中央値|改善|同率|悪化|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for metric, values in changes.items():
        unit = "°" if "angle" in metric else ""
        lines.append(
            f"|{labels[metric]}|{values['before']:.3f}{unit}|{values['after']:.3f}{unit}|"
            f"{values['improved']}|{values['equal']}|{values['worsened']}|"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
