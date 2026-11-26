"""Measure completed drawings from the recorded sifting starts."""

import argparse
from copy import deepcopy
import json
from math import factorial, isfinite, prod
from pathlib import Path
from random import Random
from statistics import median
from time import perf_counter
from unittest.mock import patch

from torus_layout import pipeline
from torus_layout.coordinates.blocks import UnsplitBlockOrderError
from torus_layout.crossing import api as crossing_api
from torus_layout.crossing import count_crossings
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult, LayerSearchResult, PipelineConfig
from torus_layout.subdivision import insert_dummy_nodes
from torus_study.geometry import route_metrics, torus_routes
from torus_study.stages import subdivision_metrics


def long_edge_starts(subdivided, seed, *, timing=False):
    layers = sorted(subdivided.layers)
    initial = crossing_api.initial_orders(subdivided.layers, layers, list(subdivided.graph.edges))[0]
    start_count = min(4, prod(factorial(len(initial[layer])) for layer in layers))
    rng = Random(100_000 + seed)
    orders = [tuple(tuple(initial[layer]) for layer in layers)]
    while len(orders) < start_count:
        option = tuple(tuple(rng.sample(initial[layer], len(initial[layer]))) for layer in layers)
        if option not in orders:
            orders.append(option)
    attempts = []
    embeddings = []
    for order in orders:
        checks = 0

        def count_work():
            nonlocal checks
            checks += 1
            return False

        start = dict(zip(layers, map(list, order), strict=True))
        result = CrossingResult(*crossing_api.sift_blocks(
            subdivided, start, layers, PipelineConfig().rounds, should_stop=count_work,
        ))
        attempts.append({"crossings": count_crossings(subdivided, result), "checks": checks})
        embeddings.append(result)
    if timing:
        samples = [[] for _ in orders]
        forward = range(len(orders))
        for indices in (forward, forward[::-1], forward):
            for index in indices:
                start = dict(zip(layers, map(list, orders[index]), strict=True))
                started = perf_counter()
                result = CrossingResult(*crossing_api.sift_blocks(
                    subdivided, start, layers, PipelineConfig().rounds,
                ))
                samples[index].append(perf_counter() - started)
                if count_crossings(subdivided, result) != attempts[index]["crossings"]:
                    raise ValueError("Timed sifting changed the crossing count")
        for attempt, times in zip(attempts, samples, strict=True):
            attempt.update(sifting_seconds=median(times), sifting_samples=times)
    return orders[1:], attempts, embeddings


def evaluate(row, *, long_edges=False, all_drawings=False, timing=False, reuse_sifting=False):
    source = row["graph"] if long_edges else row
    nodes = tuple(source["nodes"])
    edges = tuple(map(tuple, source["edges"]))
    graph = Graph(nodes, edges)
    ranks = (dict(zip(nodes, row["specified_ranks"], strict=True)) if long_edges
             else {u: u // row["width"] for u in nodes})
    flags = (dict(zip(edges, row["specified_flags"], strict=True)) if "specified_flags" in row
             else {(u, v): ranks[u] > ranks[v] for u, v in edges})
    assignment = LayerAssignmentResult(ranks, flags, 0)
    layer_count = row.get("specified_layer_count", len(set(ranks.values())))
    setup = (LayerSearchResult(layer_count, sum(flags.values()), 0), assignment)

    def measure():
        try:
            layout = pipeline.run_pipeline(graph)
        except UnsplitBlockOrderError as error:
            return {"status": "unsplit_order_error", "error": str(error)}
        paths, _ = subdivision_metrics(graph, layout.subdivided)
        routes, bounds = torus_routes(paths, layout.subdivided, layout.crossing, layout.coordinates)
        return {"seam_method": layout.seam_method_used, **route_metrics(routes, bounds)}

    if long_edges:
        subdivided = insert_dummy_nodes(graph, assignment)
        orders, attempts, embeddings = long_edge_starts(subdivided, row["seed"], timing=timing)
        details = {"case": row["id"], "dummy_nodes": len(subdivided.dummy_nodes),
                   "alternate_orders": orders, "restart_attempts": attempts}
    else:
        orders, attempts = row["alternate_orders"], row["restart_attempts"]
        details = {"width": row["width"]}
    best = min(range(len(attempts)), key=lambda i: attempts[i]["crossings"])
    with patch.object(pipeline, "assign_layers", return_value=setup):
        drawings = {}
        indices = range(len(attempts)) if all_drawings else dict.fromkeys((0, best))
        for index in indices:
            if reuse_sifting:
                cached = embeddings[index]
                with patch.object(crossing_api, "sift_blocks",
                                  side_effect=lambda *a, **kw: deepcopy((cached.order, cached.winding_numbers))):
                    drawings[index] = measure()
            elif index:
                order = dict(enumerate(map(list, orders[index - 1])))
                with patch.object(crossing_api, "initial_orders", return_value=(order,)):
                    drawings[index] = measure()
            else:
                drawings[index] = measure()
    baseline = drawings[0]
    if all_drawings:
        details["drawings"] = drawings
        if "geometric_crossings" in baseline:
            feasible = [
                i for i, d in drawings.items()
                if "geometric_crossings" in d and d["bends"] <= baseline["bends"]
                and d["either_seam_edges"] <= baseline["either_seam_edges"]
            ]
            details["selected_without_extra_bends_or_seams"] = min(
                feasible, key=lambda i: (drawings[i]["geometric_crossings"], i)
            )
    return {**details, "seed": row["seed"], "selected_start": best,
            "baseline": baseline, "selected": drawings[best]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("--long-edges", action="store_true", help="Use a fixed-rank input manifest")
    parser.add_argument("--all-drawings", action="store_true", help="Measure every recorded start")
    parser.add_argument("--timing", action="store_true", help="Time uninstrumented sifting on the fixed ranks")
    parser.add_argument("--reuse-sifting", action="store_true")
    parser.add_argument("--wall-seconds", type=float, help="Time limit per input")
    args = parser.parse_args()
    if (args.timing or args.reuse_sifting) and not args.long_edges:
        parser.error("--timing and --reuse-sifting require --long-edges")
    if args.wall_seconds is not None and (not isfinite(args.wall_seconds) or args.wall_seconds <= 0):
        parser.error("--wall-seconds must be positive and finite")
    from contextlib import nullcontext
    from run_torus_validation import BudgetExpired, wall_budget

    with args.rows.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            started = perf_counter()
            try:
                with wall_budget(args.wall_seconds) if args.wall_seconds else nullcontext():
                    result = evaluate(row, long_edges=args.long_edges, all_drawings=args.all_drawings,
                                      timing=args.timing, reuse_sifting=args.reuse_sifting)
            except BudgetExpired:
                identity = {"case": row["id"]} if args.long_edges else {"width": row["width"], "seed": row["seed"]}
                result = {**identity, "status": "wall_timeout"}
            if args.wall_seconds:
                result["wall_seconds"] = perf_counter() - started
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
