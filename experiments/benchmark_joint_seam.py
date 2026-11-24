"""Benchmark hard-zero joint seam selection against the legacy boundary phase.

Run with PYTHONPATH=src and the project interpreter. Choose "generated" for
graph-generator inputs (local Gurobi license or preset layers), or "synthetic"
for a controlled layer-width sweep. CSV output contains median milliseconds.
The joint method permits an independent common integer turn per layer pair.
"""

import argparse
import csv
from collections import defaultdict
from itertools import product
from math import inf, prod
from random import Random
from statistics import median
import sys
from time import perf_counter_ns

from generator import generate_graph
from torus_layout.crossing import count_crossings, optimize_joint_seam, reduce_crossings
from torus_layout.crossing.api import _process_boundaries
from torus_layout.crossing.seam import optimize_seam, seam_score
from torus_layout.layering import assign_layers
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult, SubdividedGraph
from torus_layout.subdivision import insert_dummy_nodes


GENERATORS = {
    "cyclic": {"edge_prob": 0.04},
    "dag": {"edge_prob": 0.35},
    "mixed": {"edge_prob": 0.18},
    "random": {"edge_prob": 0.16},
    "watts_strogatz": {"k": 4, "p": 0.1},
}


def exhaustive(graph, crossing):
    layers = sorted(crossing.order)
    location = {u: (layer, rank, len(crossing.order[layer])) for layer in layers
                for rank, u in enumerate(crossing.order[layer])}
    dummy = graph.dummy_nodes
    best = inf
    for cuts in product(*(range(max(1, len(crossing.order[layer]))) for layer in layers)):
        gaps = dict(zip(layers, cuts))
        strips = defaultdict(list)
        for u, v in graph.graph.edges:
            a, p, n = location[u]
            b, q, k = location[v]
            lift = q + k * crossing.winding_numbers.get((u, v), 0)
            value = (lift - gaps[b]) // k - (p - gaps[a]) // n
            strips[min(a, b), max(a, b)].append((value if a < b else -value, u in dummy and v in dummy))
        total = 0
        for segments in strips.values():
            choices = {w for w, _ in segments}
            feasible = [sum(w != offset for w, _ in segments) for offset in choices
                        if all(w == offset for w, internal in segments if internal)]
            total += min(feasible, default=inf)
        best = min(best, total)
    return None if best == inf else (0, best)


def timed(function, repeats):
    result = function()
    times = []
    for _ in range(repeats):
        started = perf_counter_ns()
        function()
        times.append((perf_counter_ns() - started) / 1e6)
    return result, median(times)


def evaluate(kind, n, seed, graph, crossing, repeats=7):
    def key(result):
        return None if result is None else seam_score(graph, result, True)

    dummy = graph.dummy_nodes
    fixed, fixed_ms = timed(lambda: optimize_seam(graph, crossing, prioritize_internal=True), repeats)
    current, current_ms = timed(lambda: _process_boundaries(graph, crossing, True, True, True, seam_method="legacy"), repeats)
    joint, joint_ms = timed(lambda: optimize_joint_seam(graph, crossing), repeats)
    combinations = prod(max(1, len(nodes)) for nodes in crossing.order.values())
    checked = combinations <= 700
    if checked:
        assert key(joint) == exhaustive(graph, crossing), (kind, n, seed, key(joint))
    assert joint is not None or key(current)[0] > 0
    if joint is not None:
        assert key(joint)[0] == 0
        assert count_crossings(graph, crossing) == count_crossings(graph, joint)
        if key(current)[0] == 0:
            # Re-running the existing DP from a rotated result can generate a
            # larger left-rotation lift but its extra turns fit joint offsets.
            assert key(joint) <= key(current), (kind, n, seed, key(joint), key(current))
    return (kind, n, seed, len(graph.graph.nodes), len(graph.graph.edges), len(graph.layers),
            max(map(len, graph.layers.values())), len(dummy),
            sum(u in dummy and v in dummy for u, v in graph.graph.edges),
            checked, key(fixed), key(current), key(joint), fixed_ms, current_ms, joint_ms)


def synthetic(width, seed, feasible=True, layer_count=8):
    rng = Random(seed)
    layers = {i: list(range(i * width, (i + 1) * width)) for i in range(layer_count)}
    dummy_count = width // 2
    nodes = tuple(u for group in layers.values() for u in group)
    dummy = set(layers[2][:dummy_count] + layers[3][:dummy_count])
    original = tuple(u for u in nodes if u not in dummy)
    paths = [
        (layers[1][i], layers[2][i], layers[3][i], layers[4 % layer_count][i])
        for i in range(dummy_count)
    ]
    edges = [edge for path in paths for edge in zip(path, path[1:])]
    for i, layer in layers.items():
        target = [v for v in layers[(i + 1) % len(layers)] if v not in dummy]
        edges.extend((u, v) for u in layer if u not in dummy for v in rng.sample(target, min(len(target), 3)))
    inner = [e for e in edges if e[0] in dummy and e[1] in dummy]
    winding = {edge: rng.choice([-1, 0, 0, 0, 1]) for edge in edges}
    winding.update(dict.fromkeys(inner, 1))
    if not feasible:
        winding[inner[0]] += 3
    return SubdividedGraph(Graph(nodes, tuple(edges)), layers, {}, {}, original), CrossingResult(layers, winding)


def preset_assignment(graph, layer_count):
    """Spread vertices over fixed cyclic layers for boundary-only benchmarks."""
    if layer_count > len(graph.nodes):
        raise ValueError("preset layer count exceeds the number of original vertices")
    neighbors = defaultdict(set)
    for u, v in graph.edges:
        neighbors[u].add(v)
        neighbors[v].add(u)
    ranks = {}
    for index, node in enumerate(graph.nodes):
        used = {ranks[neighbor] for neighbor in neighbors[node] if neighbor in ranks}
        available = ((index + offset) % layer_count for offset in range(layer_count))
        rank = next((layer for layer in available if layer not in used), None)
        if rank is None:
            raise ValueError("preset layer count is too small for the generated graph")
        ranks[node] = rank
    return LayerAssignmentResult(ranks, {(u, v): ranks[u] > ranks[v] for u, v in graph.edges}, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("generated", "synthetic"))
    parser.add_argument("--sizes", type=int, nargs="+", help="original vertices or synthetic layer widths")
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--families", choices=tuple(GENERATORS), nargs="+", default=tuple(GENERATORS))
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--rounds", type=int, default=2, help="global sifting rounds for generated inputs")
    parser.add_argument("--preset-layers", type=int, help="use fixed cyclic layers instead of Gurobi")
    parser.add_argument("--edge-prob", type=float, help="override edge probability for applicable generators")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.rounds < 0:
        parser.error("--rounds must be nonnegative")
    if args.preset_layers is not None and args.preset_layers < 2:
        parser.error("--preset-layers must be at least 2")
    writer = csv.writer(sys.stdout)
    writer.writerow(('kind','n','seed','nodes','segments','layers','max_width','dummy_nodes','inner_segments',
                     'exhaustive','fixed','current','joint','fixed_ms','current_ms','joint_ms'))
    sys.stdout.flush()
    if args.dataset == "generated":
        for kind in args.families:
            options = dict(GENERATORS[kind])
            if args.edge_prob is not None and "edge_prob" in options:
                options["edge_prob"] = args.edge_prob
            for n, seed in product(args.sizes or (5, 7, 9, 12), args.seeds or range(4)):
                nodes, edges, _ = generate_graph(kind, n, seed=seed, **options)
                original = Graph(tuple(nodes), tuple(edges))
                if args.preset_layers is None:
                    with use_local_license():
                        assigned = assign_layers(original, 'diff')
                    assert assigned is not None
                    assignment = assigned[1]
                else:
                    assignment = preset_assignment(original, args.preset_layers)
                graph = insert_dummy_nodes(original, assignment)
                crossing = reduce_crossings(graph, rounds=args.rounds, sifting_method='global',
                                            optimize_seams=False, unwind=False, algo2=False)
                writer.writerow(evaluate(kind, n, seed, graph, crossing, args.repeats))
                sys.stdout.flush()
    else:
        for width, seed in product(args.sizes or (2, 4, 8, 16, 32, 64), args.seeds or range(3)):
            writer.writerow(evaluate('synthetic', width, seed, *synthetic(width, seed), args.repeats))
            sys.stdout.flush()
        graph, crossing = synthetic(2, 0, layer_count=4)
        dummy = graph.dummy_nodes
        inner = next(edge for edge in graph.graph.edges if set(edge) <= dummy)
        crossing = CrossingResult(crossing.order, crossing.winding_numbers | {inner: 3})
        writer.writerow(evaluate('requires_unwind', 2, 0, graph, crossing))
        writer.writerow(evaluate('infeasible', 4, 0, *synthetic(4, 0, feasible=False, layer_count=4)))

if __name__ == '__main__':
    main()
