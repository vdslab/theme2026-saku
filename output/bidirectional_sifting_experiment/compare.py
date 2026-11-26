"""Compare forward-only and bidirectional sifting without changing production."""

import json
from pathlib import Path
from unittest.mock import patch

from torus_layout.models import Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import api
from torus_layout.crossing.sifting import sift_two_layer_pair
from torus_layout.crossing.lib.embedding import copy_order, forward_layer_pairs
from torus_layout.crossing.lib.crossings import count_all_crossings, crossings_between_edges
from torus_layout.coordinates.replicated import compute_unprojected_coordinates
from torus_layout.drawing import DrawingOptions, draw_layout


def bidirectional(mode):
    def run(order, psi, layers, edges, rounds, dummy_nodes=None, optimize_winding=True):
        best_order, best_psi = copy_order(order), dict(psi)
        best_count = count_all_crossings(order, psi, layers, edges)
        forward = forward_layer_pairs(layers)
        reverse = [(b, a) for a, b in reversed(forward)]
        steps = (
            [pair for pair in forward + reverse for _ in range(rounds)]
            if mode == "reverse_second_pass"
            else (forward + reverse) * rounds
        )
        for fixed, free in steps:
            sift_two_layer_pair(
                fixed, free, order, psi, edges,
                dummy_nodes=dummy_nodes, optimize_winding=optimize_winding,
            )
            count = count_all_crossings(order, psi, layers, edges)
            if count < best_count:
                best_order, best_psi, best_count = copy_order(order), dict(psi), count
        order.clear()
        order.update(best_order)
        psi.clear()
        psi.update(best_psi)
    return run


def original_edge_crossings(graph, crossing, first=(24, 1), second=(24, 3)):
    original = set(graph.original_nodes)
    outgoing = {}
    for u, v in graph.graph.edges:
        outgoing.setdefault(u, []).append(v)
    def chain(target):
        for v in outgoing.get(target[0], []):
            path = [target[0], v]
            while path[-1] not in original:
                path.append(outgoing[path[-1]][0])
            if path[-1] == target[1]:
                return list(zip(path, path[1:]))
        return []
    position = {n: i for ns in crossing.order.values() for i, n in enumerate(ns)}
    layer_of = {n: l for l, ns in crossing.order.items() for n in ns}
    return sum(
        crossings_between_edges(a, b, position, position, crossing.winding_numbers)
        for a in chain(first) for b in chain(second)
        if layer_of[a[0]] == layer_of[b[0]] and layer_of[a[1]] == layer_of[b[1]]
    )


def main():
    output = Path(__file__).resolve().parent
    paths = [Path("output/torus_layout_bk_unprojected/result.json"),
             Path("output/bk_3x3_experiment/bk_unprojected.json"),
             Path("output/unwind_missing_inner_fix/result.json"),
             Path("output/unwind_cli_check/result.json")]
    reports = []
    for index, path in enumerate(paths):
        data = json.loads(path.read_text())
        ranks = dict(data["layer_assignment"])
        edges = tuple(map(tuple, data["input_graph"]["edges"]))
        graph = insert_dummy_nodes(
            Graph(tuple(data["input_graph"]["nodes"]), edges),
            LayerAssignmentResult(ranks, {e: ranks[e[1]] <= ranks[e[0]] for e in edges}, 0),
        )
        assert graph.graph.edges == tuple((s["source"], s["target"]) for s in data["segments"])
        report = {"input": str(path), "seed": data["settings"]["seed"], "methods": {}}
        for mode in ("current", "reverse_second_pass", "alternating_sweeps"):
            for rounds in (5, 10):
                kwargs = dict(rounds=rounds, optimize_seams=True, unwind=True)
                if mode == "current":
                    crossing = api.reduce_crossings(graph, **kwargs)
                else:
                    with patch.object(api, "run_sifting_with_global_guard", bidirectional(mode)):
                        crossing = api.reduce_crossings(graph, **kwargs)
                result = {"total_crossings": api.count_crossings(graph, crossing),
                          "24_1_vs_24_3_crossings": original_edge_crossings(graph, crossing)}
                report["methods"][f"{mode}_{rounds}"] = result
                if index == 0 and rounds == 5:
                    coordinates = compute_unprojected_coordinates(graph, crossing, min_gap=1.0)
                    draw_layout(graph, crossing, coordinates,
                                options=DrawingOptions(tile_surroundings=True),
                                save_path=output / f"{mode}.png", show=False)
                    (output / f"{mode}_embedding.json").write_text(json.dumps({
                        "order": list(crossing.order.items()),
                        "segments": [{"source": u, "target": v, "winding": crossing.winding_numbers.get((u,v),0)} for u,v in graph.graph.edges],
                        "period": coordinates.period,
                        "coordinates": [[n,x,y] for n,(x,y) in coordinates.positions.items()],
                    }, indent=2) + "\n")
        reports.append(report)
        print(json.dumps(report), flush=True)
    (output / "comparison.json").write_text(json.dumps(reports, indent=2) + "\n")


if __name__ == "__main__":
    main()
