"""Profile equal-work global sifting on a saved large input."""

import argparse
from contextlib import nullcontext
import cProfile
from functools import partial
import json
from pathlib import Path
from pstats import Stats
from time import perf_counter
from unittest.mock import patch

from torus_layout.crossing import global_sifting
from torus_layout.crossing.initialization import initial_orders
from torus_layout.models import Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes

from torus_study.square_cut import minimize_square_ranks
from torus_study.vector_sifting import vector_parting_costs
from torus_study.wrap_bounds import feasible_wrap_assignment, improve_wrap_assignment


MODES = ("integer", "vector", "vector_cached", "vector_incremental", "vector_delta")


def profile(manifest, limit, modes):
    graph = Graph(tuple(manifest["graph"]["nodes"]), tuple(map(tuple, manifest["graph"]["edges"])))
    _, assignment = feasible_wrap_assignment(graph)
    assignment = improve_wrap_assignment(graph, assignment)
    ranks, _ = minimize_square_ranks(
        graph, max(assignment.node_to_layer.values()) + 1, assignment, scaled=True
    )
    proper = insert_dummy_nodes(graph, LayerAssignmentResult(ranks, assignment.torus_flags, 0))
    layers = sorted(proper.layers)
    initial = initial_orders(proper.layers, layers, list(proper.graph.edges))[0]
    reference = None
    for mode in modes:
        checks = 0

        def stop():
            nonlocal checks
            checks += 1
            return checks >= limit

        scorer = nullcontext() if mode == "integer" else patch.object(
            global_sifting, "_strip_score", partial(global_sifting._strip_score, bulk_costs=vector_parting_costs)
        )
        profiler = cProfile.Profile()
        with scorer:
            started = perf_counter()
            outcome = profiler.runcall(
                global_sifting.sift_blocks, proper, initial, layers, 5,
                sparse_candidates=True, integer_scoring=True, should_stop=stop,
                cache_strip_scores=mode in ("vector_cached", "vector_incremental", "vector_delta"),
                incremental_orders=mode in ("vector_incremental", "vector_delta"),
                incremental_scores=mode == "vector_delta",
            )
            elapsed = perf_counter() - started
        if reference is None:
            reference = outcome
        assert reference == outcome and checks == limit
        stats = Stats(profiler)
        detail = [
            {"file": Path(key[0]).name, "line": key[1], "function": key[2],
             "calls": values[1], "self_seconds": values[2], "cumulative_seconds": values[3]}
            for key, values in sorted(stats.stats.items(), key=lambda entry: -entry[1][3])
        ]
        yield {"case": manifest["id"], "mode": mode, "checks": checks,
               "segments": len(proper.graph.edges), "wall_seconds": elapsed,
               "equal_order_and_winding": True, "functions": detail}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("case")
    parser.add_argument("--checks", type=int, default=1000)
    parser.add_argument("--mode", nargs="+", choices=MODES, default=MODES)
    args = parser.parse_args()
    if args.checks < 1:
        parser.error("checks must be positive")
    with args.inputs.open(encoding="utf-8") as source:
        manifest, = [row for row in map(json.loads, source) if row["id"] == args.case]
    for row in profile(manifest, args.checks, args.mode):
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
