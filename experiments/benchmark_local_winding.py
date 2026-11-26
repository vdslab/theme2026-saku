"""Measure the existing and experimental scorers on representative strips."""

import argparse
import json
from random import Random
from statistics import median
from time import perf_counter

from torus_layout.crossing.global_sifting import _strip_score


def benchmark_strips(vector=False):
    for width in (24, 64, 128):
        rng = Random(width)
        left, right = list(range(width)), list(range(width, 2 * width))
        order = {0: left, 1: right}
        variable = {(u, right[0]) for u in left[:4]}
        possible = [(u, v) for u in left for v in right[1:]]
        segments = sorted(variable) + rng.sample(possible, 2 * width)
        winding = {edge: rng.choice((-1, 0, 1)) for edge in segments}
        winding.update({(-u - 1, -u - 2): 0 for u in range(8000)})
        args = order, winding, (0, 1), segments, variable
        options = {"baseline": {}, "local": {"local_winding": True},
                   "integer": {"integer_scoring": True}}
        if vector:
            from torus_study.vector_sifting import vector_parting_costs

            options["vector"] = {"integer_scoring": True, "bulk_costs": vector_parting_costs}
        expected = _strip_score(*args, moving=variable)
        assert all(_strip_score(*args, moving=variable, **kwargs) == expected
                   for kwargs in options.values())

        times = {name: [] for name in options}
        names = list(options)
        for repeat in range(9):
            offset = repeat % len(names)
            for name in names[offset:] + names[:offset]:
                start = perf_counter()
                for _ in range(40):
                    _strip_score(*args, moving=variable, **options[name])
                times[name].append((perf_counter() - start) / 40)
        print(json.dumps({
            "width": width, "segment_count": len(segments), "winding_entries": len(winding),
            "repeats": 9, "calls_per_repeat": 40,
            **{f"{name}_median_seconds": median(values) for name, values in times.items()},
        }))


def check_fixed_ranks(vector=False):
    from contextlib import nullcontext
    from functools import partial
    from unittest.mock import patch

    from torus_layout.crossing import global_sifting
    from torus_layout.crossing.initialization import initial_orders
    from torus_layout.models import LayerAssignmentResult
    from torus_layout.subdivision import insert_dummy_nodes
    from torus_study.validation_inputs import trials

    for trial in trials("fixed_rank_sparse", None, None):
        graph = trial.case.graph
        if len(graph.nodes) != 100:
            continue
        width = trial.extra["layer_width"]
        ranks = {u: u // width for u in graph.nodes}
        flags = {(u, v): ranks[u] > ranks[v] for u, v in graph.edges}
        sub = insert_dummy_nodes(graph, LayerAssignmentResult(ranks, flags, 0))
        layers = sorted(sub.layers)
        initial = initial_orders(sub.layers, layers, list(sub.graph.edges))[0]
        outcomes = []
        configs = ({}, {"sparse_candidates": True, "integer_scoring": True})
        if vector:
            from torus_study.vector_sifting import vector_parting_costs
            configs += ({"sparse_candidates": True, "integer_scoring": True, "cache_strip_scores": True},)
        for index, settings in enumerate(configs):
            context = nullcontext() if index != 2 else patch.object(
                global_sifting, "_strip_score",
                partial(global_sifting._strip_score, bulk_costs=vector_parting_costs),
            )
            with context:
                start = perf_counter()
                result = global_sifting.sift_blocks(sub, initial, layers, 5, **settings)
                outcomes.append((result, perf_counter() - start))
        assert all(outcomes[0][0] == result for result, _ in outcomes[1:])
        print(json.dumps({
            "case": trial.case.id, "equal_orders_and_windings": True,
            "baseline_seconds": outcomes[0][1], "integer_sparse_seconds": outcomes[1][1],
            **({"vector_cached_seconds": outcomes[2][1]} if vector else {}),
        }))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-rank-check", action="store_true")
    parser.add_argument("--vector", action="store_true")
    args = parser.parse_args()
    if args.fixed_rank_check:
        check_fixed_ranks(args.vector)
    else:
        benchmark_strips(args.vector)


if __name__ == "__main__":
    main()
