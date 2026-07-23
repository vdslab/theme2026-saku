"""アブレーション実験の代表描画を生成する。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from drawing.draw_radial_torus import draw_radial_torus
from layer_assignment.torus_balance import balance_layer_assignment
from layer_assignment.torus_binary_search import find_minimum_torus_configuration

from evaluate_layer_count_search import generate_graph
from evaluate_torus_framework_ablation import (
    OUTPUT_DIR,
    coordinate_variant,
    prepare_embedding,
    run_crossing_variant,
)


NODES = 20
FAMILY = "mixed"
SEED = 1


def save_drawing(
    path: Path,
    vertices,
    order,
    layers,
    edges,
    torus_edges,
    psi,
    positions,
):
    draw_radial_torus(
        V=vertices,
        A=edges,
        L=layers,
        order=order,
        psi=psi,
        t_val=torus_edges,
        pos=positions,
        save_path=path,
        show=False,
        draw_dummy_nodes=False,
        show_legend=False,
        show_layer_labels=True,
        node_size=150,
        font_size=6,
        edge_width=0.7,
        dpi=220,
    )


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    vertices, edges = generate_graph(FAMILY, NODES, SEED)
    edges = sorted(set(edges))
    layer_count, torus_count, _ = find_minimum_torus_configuration(vertices, edges)
    y_val, t_val, layer_dict, _ = balance_layer_assignment(
        vertices, edges, torus_count, layer_count, "diff_square"
    )
    if not y_val:
        raise RuntimeError("representative layer assignment failed")
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

    crossing_variants = (
        ("order_only", "Fixed psi"),
        ("joint_psi", "Joint psi"),
        ("full_guard_rotation", "Full integration"),
    )
    images = []
    full_order = None
    full_psi = None
    for variant, title in crossing_variants:
        order, psi, crossings, _runtime = run_crossing_variant(prepared, variant)
        positions, _runtime, _metrics = coordinate_variant(
            "bk_torus_smoothing",
            vertices,
            order,
            layers,
            dummy_layers,
            dummy_edges,
            dummy_torus,
            psi,
        )
        path = OUTPUT_DIR / f"example-crossing-{variant}.png"
        save_drawing(
            path,
            vertices,
            order,
            dummy_layers,
            dummy_edges,
            dummy_torus,
            psi,
            positions,
        )
        images.append((path, f"{title} (crossings={crossings})"))
        if variant == "full_guard_rotation":
            full_order, full_psi = order, psi

    for variant, title in (
        ("uniform", "Uniform coordinates"),
        ("bk_no_smoothing", "BK coordinates"),
        ("bk_torus_smoothing", "BK + torus smoothing"),
    ):
        positions, _runtime, metrics = coordinate_variant(
            variant,
            vertices,
            full_order,
            layers,
            dummy_layers,
            dummy_edges,
            dummy_torus,
            full_psi,
        )
        path = OUTPUT_DIR / f"example-coordinate-{variant}.png"
        save_drawing(
            path,
            vertices,
            full_order,
            dummy_layers,
            dummy_edges,
            dummy_torus,
            full_psi,
            positions,
        )
        images.append((path, f"{title} (mean length={metrics['mean_edge_length']:.2f})"))

    figure, axes = plt.subplots(2, 3, figsize=(15, 8.3))
    figure.suptitle(
        f"Representative final drawings (n={NODES}, {FAMILY}, seed={SEED})",
        fontsize=16,
    )
    for axis, (path, title) in zip(axes.flat, images):
        axis.imshow(mpimg.imread(path))
        axis.set_title(title)
        axis.set_axis_off()
    figure.tight_layout()
    figure.savefig(
        OUTPUT_DIR / "final-drawing-ablation.png",
        dpi=220,
        bbox_inches="tight",
    )
    plt.close(figure)


if __name__ == "__main__":
    run()
