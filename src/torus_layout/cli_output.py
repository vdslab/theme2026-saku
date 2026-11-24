"""Save CLI images and reproducible results, then optionally display them."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .models import Graph, PipelineConfig, PipelineResult
from .reporting import boundary_metrics
from .seam_comparison import SeamComparison


def save_outputs(
    args: argparse.Namespace,
    graph: Graph,
    config: PipelineConfig,
    result: PipelineResult,
    comparison: SeamComparison,
    parameters: dict[str, int | float],
    used_seed: int,
    computation_seconds: float,
) -> None:
    from .drawing import DrawingOptions, draw_layout

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    options = DrawingOptions(
        draw_dummy_nodes=args.draw_dummy_nodes,
        tile_surroundings=args.tile_surroundings,
    )
    draw_layout(
        result.subdivided,
        result.crossing,
        result.coordinates,
        options=options,
        save_path=output / "layout.png",
        show=False,
    )
    if comparison.baseline is not None and comparison.baseline_coordinates is not None:
        draw_layout(
            result.subdivided,
            comparison.baseline,
            comparison.baseline_coordinates,
            options=options,
            save_path=output / "before_seam.png",
            show=False,
        )
    settings = {
        "graph": args.graph,
        "nodes": args.nodes,
        "seed": used_seed,
        "generator_parameters": parameters,
        "pipeline": asdict(config),
        "seam_method_used": result.seam_method_used,
        "license_mode": "local" if args.local_license else "application_env",
        "compare_seams": args.compare_seams,
        "drawing": asdict(options),
    }
    metrics = {
        "original_nodes": len(graph.nodes),
        "original_edges": len(graph.edges),
        "subdivided_nodes": len(result.subdivided.graph.nodes),
        "segments": len(result.subdivided.graph.edges),
        "max_proper_layer_size": max(map(len, result.subdivided.layers.values()), default=0),
        **boundary_metrics(result.subdivided, result.crossing.winding_numbers),
        "layers": len(result.crossing.order),
        "seam_segments": comparison.after_seams,
        "crossings": comparison.after_crossings,
        "seam_segments_before": comparison.before_seams,
        "crossings_before": comparison.before_crossings,
        "layer_search_seconds": result.search.runtime,
        "layer_search_solver_seconds": result.search.solver_time,
        "layer_search_solver_status": result.search.solver_status,
        "balance_seconds": result.balance_time,
        "balance_solver_seconds": result.assignment.solver_time,
        "balance_solver_status": result.assignment.solver_status,
        "subdivision_seconds": result.subdivision_time,
        "crossing_seconds": result.crossing_time,
        "coordinate_seconds": result.coordinate_time,
        "computation_wall_seconds": computation_seconds,
    }
    # Arrays preserve node IDs and edge occurrences without JSON tuple-key coercion.
    payload = {
        "status": "completed",
        "settings": settings,
        "metrics": metrics,
        "input_graph": {"nodes": graph.nodes, "edges": graph.edges},
        "layer_assignment": [
            [node, layer] for node, layer in result.assignment.node_to_layer.items()
        ],
        "order": [[layer, group] for layer, group in result.crossing.order.items()],
        "segments": [
            {
                "source": u,
                "target": v,
                "winding": result.crossing.winding_numbers.get((u, v), 0),
                "horizontal_wrap": result.subdivided.torus_flags.get((u, v), False),
            }
            for u, v in result.subdivided.graph.edges
        ],
        "coordinates": [
            [node, x, y] for node, (x, y) in result.coordinates.positions.items()
        ],
        "period": result.coordinates.period,
    }
    (output / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"画像: {output / 'layout.png'}")
    if comparison.baseline is not None:
        print(f"比較画像: {output / 'before_seam.png'}")
    print(f"設定・グラフ・座標・評価値: {output / 'result.json'}", flush=True)
    if args.show:
        _show_saved_image(output / "layout.png")


def _show_saved_image(path: Path) -> None:
    """Display the saved result after every output file has been written."""
    from PIL import Image
    from torus_layout.drawing.output import show_image

    with Image.open(path) as image:
        show_image(image)
