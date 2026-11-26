"""Replay saved embeddings, so only the coordinate method changes."""

import json
import math
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from torus_layout.coordinates import assign_coordinates
from torus_layout.coordinates.replicated import (
    expand_3x3, compute_replica_positions, compute_unprojected_coordinates,
)
from torus_layout.drawing import DrawingOptions, draw_layout
from torus_layout.models import CoordinateResult, CrossingResult, Graph, SubdividedGraph


def load_graph(path):
    data = json.loads(path.read_text())
    order = dict(data["order"])
    edges = tuple((e["source"], e["target"]) for e in data["segments"])
    graph = SubdividedGraph(
        Graph(tuple(n for ns in order.values() for n in ns), edges), order,
        {(e["source"], e["target"]): e["horizontal_wrap"] for e in data["segments"]},
        {e: 1.0 for e in edges}, tuple(data["input_graph"]["nodes"]),
    )
    crossing = CrossingResult(
        order, {(e["source"], e["target"]): e["winding"] for e in data["segments"]},
    )
    return data, graph, crossing


def metrics(graph, crossing, coordinates):
    out = defaultdict(list)
    for u, v in graph.graph.edges:
        out[u].append(v)
    chains = []
    for source in graph.original_nodes:
        for target in out[source]:
            chain = [source, target]
            while chain[-1] in graph.dummy_nodes:
                chain.append(out[chain[-1]][0])
            if len(chain) > 2:
                chains.append(chain)
    slopes = {
        (u, v): coordinates.positions[v][1] - coordinates.positions[u][1]
        + coordinates.period * crossing.winding_numbers.get((u, v), 0)
        for u, v in graph.graph.edges
    }
    bends = []
    details = []
    for chain in chains:
        ds = [slopes[u, v] for u, v in zip(chain, chain[1:])]
        count = sum(abs(b - a) > 1e-7 for a, b in zip(ds, ds[1:]))
        bends.append(count)
        details.append({"edge": [chain[0], chain[-1]], "bends": count})
    return {
        "period": coordinates.period,
        "long_edges": len(chains),
        "edges_above_two_bends": sum(b > 2 for b in bends),
        "max_bends": max(bends, default=0),
        "total_bends": sum(bends),
        "squared_vertical_displacement": sum(d * d for d in slopes.values()),
        "edge_bends": details,
    }


def run():
    output = Path(__file__).resolve().parent
    inputs = [Path("output/torus_layout/result.json"),
              Path("output/unwind_missing_inner_fix/result.json"),
              Path("output/unwind_cli_check/result.json")]
    report = []
    for index, path in enumerate(inputs):
        data, graph, crossing = load_graph(path)
        case = {"input": str(path), "seed": data["settings"]["seed"], "methods": {}}
        for method in ("brandes_koepf", "bk_unprojected", "brandes_koepf_3x3"):
            started = perf_counter()
            coordinates = (
                compute_unprojected_coordinates(graph, crossing, min_gap=1.0)
                if method == "bk_unprojected"
                else assign_coordinates(graph, crossing, method=method)
            )
            elapsed = perf_counter() - started
            result = metrics(graph, crossing, coordinates)
            result["seconds"] = elapsed
            case["methods"][method] = result
            if index == 0:
                draw_layout(
                    graph, crossing, coordinates,
                    options=DrawingOptions(tile_surroundings=True),
                    save_path=output / f"{method}.png", show=False,
                )
                payload = json.loads(json.dumps(data))
                payload["settings"]["pipeline"]["coordinate_method"] = method
                payload["coordinates"] = [[n, x, y] for n, (x, y) in coordinates.positions.items()]
                payload["period"] = coordinates.period
                # Previous pipeline metrics describe the saved input, not this replay.
                payload["metrics"]["coordinate_seconds"] = elapsed
                payload["metrics"]["computation_wall_seconds"] = None
                (output / f"{method}.json").write_text(json.dumps(payload, indent=2) + "\n")
        expanded = expand_3x3(graph, crossing)
        positions = compute_replica_positions(expanded)
        period = case["methods"]["brandes_koepf_3x3"]["period"]
        errors = []
        for (node, horizontal, vertical), replica_id in expanded.node_ids.items():
            if horizontal == vertical == 0:
                continue
            central_y = positions[expanded.node_ids[node, 0, 0]][1]
            errors.append(positions[replica_id][1] - central_y - vertical * period)
        case["replica_consistency"] = {
            "rms_y_translation_error": math.sqrt(sum(e * e for e in errors) / len(errors)),
            "max_y_translation_error": max(map(abs, errors)),
            "omitted_outer_segments": expanded.omitted_segments,
            "central_segments_missing_target_copy": sum(
                (v, int(graph.torus_flags.get((u, v), False)), crossing.winding_numbers.get((u, v), 0))
                not in expanded.node_ids for u, v in graph.graph.edges
            ),
        }
        if index == 0:
            ys = [y for _, y in positions.values()]
            cover_period = max(max(map(len, expanded.graph.layers.values())), max(ys) - min(ys) + 1)
            draw_layout(
                expanded.graph, expanded.crossing, CoordinateResult(positions, cover_period),
                options=DrawingOptions(node_size=35, dummy_node_size=5, font_size=3, dpi=300),
                save_path=output / "expanded_3x3.png", show=False,
            )
        report.append(case)
        print(json.dumps({k: v for k, v in case.items() if k != "methods"}))
        for method, values in case["methods"].items():
            print(method, {k: v for k, v in values.items() if k != "edge_bends"})
    (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    run()
