"""Exhaust layer orders and bounded windings on small unit-span graphs."""

import argparse
import json
from fractions import Fraction
from itertools import combinations, permutations, product
from math import ceil, floor
from random import Random

from torus_layout.crossing import count_crossings
from torus_layout.crossing.global_sifting import sift_blocks
from torus_layout.crossing.initialization import initial_orders
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes


def strip_minimum(edges, left, right, bound):
    left_height = {u: Fraction(i, len(left)) for i, u in enumerate(left)}
    right_height = {v: Fraction(i, len(right)) for i, v in enumerate(right)}
    pairs = [
        (i, j, left_height[a] - left_height[u], right_height[b] - right_height[v])
        for (i, (u, v)), (j, (a, b)) in combinations(enumerate(edges), 2)
    ]
    # Each crossing is an integer strictly between the two lifted differences.
    pair_cost = [
        (i, j, {
            delta: max(0, ceil(max(start, end + delta)) - floor(min(start, end + delta)) - 1)
            for delta in range(-2 * bound, 2 * bound + 1)
        })
        for i, j, start, end in pairs
    ]
    return min(
        (sum(cost[w[j] - w[i]] for i, j, cost in pair_cost), w)
        for w in product(range(-bound, bound + 1), repeat=len(edges))
    )


def exact(sub, strips, bound):
    orders = [list(permutations(layer)) for layer in sub.layers.values()]
    tables = [
        {(a, b): strip_minimum(edges, a, b, bound)
         for a, b in product(orders[i], orders[(i + 1) % len(orders)])}
        for i, edges in enumerate(strips)
    ]
    score, selected = min(
        (sum(table[c[i], c[(i + 1) % len(c)]][0] for i, table in enumerate(tables)), c)
        for c in product(*orders)
    )
    witness = {}
    for i, (edges, table) in enumerate(zip(strips, tables, strict=True)):
        w = table[selected[i], selected[(i + 1) % len(selected)]][1]
        witness.update(zip(edges, w, strict=True))
    embedding = CrossingResult(dict(enumerate(map(list, selected))), witness)
    if count_crossings(sub, embedding) != score:
        raise ValueError("Independent oracle and implementation disagree on the witness")
    return score, embedding


def trial(width, strip_size, seed, *, restarts=False):
    rng = Random(seed)
    layers = 3
    nodes = tuple(range(width * layers))
    groups = [nodes[i:i + width] for i in range(0, len(nodes), width)]
    strips = [
        sorted(rng.sample(list(product(group, groups[(i + 1) % layers])), strip_size))
        for i, group in enumerate(groups)
    ]
    edges = tuple(edge for strip in strips for edge in strip)
    ranks = {u: u // width for u in nodes}
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    sub = insert_dummy_nodes(Graph(nodes, edges), LayerAssignmentResult(ranks, flags, 0))
    initial = initial_orders(sub.layers, sorted(sub.layers), list(sub.graph.edges))[0]
    history = {}
    for rounds in (0, 1, 5):
        order, winding = sift_blocks(sub, initial, sorted(sub.layers), rounds)
        assert all(abs(w) <= 1 for w in winding.values())
        history[rounds] = count_crossings(sub, CrossingResult(order, winding))
    minimum, witness = exact(sub, strips, 1)
    extended, _ = exact(sub, strips, 2)
    assert extended <= minimum <= min(history.values())
    result = {
        "width": width, "seed": seed, "nodes": nodes, "edges": edges,
        "crossings_by_pass_limit": history, "minimum_winding_1": minimum,
        "minimum_winding_2": extended, "gap_after_5": history[5] - minimum,
        "witness_order": witness.order,
        "witness_windings": [witness.winding_numbers[e] for e in edges],
    }
    if restarts:
        layer_ids = sorted(sub.layers)
        starts = list(product(*(permutations(sub.layers[layer]) for layer in layer_ids)))
        canonical = tuple(tuple(initial[layer]) for layer in layer_ids)
        starts.remove(canonical)

        def search(start, rounds):
            checks = 0

            def count_work():
                nonlocal checks
                checks += 1
                return False

            order, winding = sift_blocks(sub, start, layer_ids, rounds, should_stop=count_work)
            return {"crossings": count_crossings(sub, CrossingResult(order, winding)), "checks": checks}

        alternates = Random(100_000 + seed).sample(starts, 3)
        attempts = [search(initial, 5)]
        attempts.extend(search(dict(zip(layer_ids, map(list, start), strict=True)), 5)
                        for start in alternates)
        assert attempts[0]["crossings"] == history[5]
        result.update(
            alternate_orders=alternates,
            restart_attempts=attempts,
            best_with_restarts=min(a["crossings"] for a in attempts),
            extended_single_start=search(initial, 20),
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restarts", action="store_true")
    parser.add_argument("--holdout", action="store_true")
    args = parser.parse_args()
    for width, strip_size in ((2, 3), (3, 5)):
        seeds = range(981, 1100) if args.holdout else range(961, 973)
        seen = set()
        if args.holdout:
            seen.update(trial(width, strip_size, seed)["edges"] for seed in range(961, 973))
        emitted = 0
        for seed in seeds:
            result = trial(width, strip_size, seed, restarts=args.restarts)
            if args.holdout and result["edges"] in seen:
                continue
            seen.add(result["edges"])
            print(json.dumps(result), flush=True)
            emitted += 1
            if emitted == 12:
                break
        if emitted != 12:
            raise RuntimeError(f"Insufficient distinct inputs for width {width}")
