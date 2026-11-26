"""Exhaustively check all feasible wrap counts of small rank assignments."""

import json
from itertools import product
from random import Random

import gurobipy as gp
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.models import Graph

from torus_study.square_epigraph import optimize_square_epigraph
from torus_study.stages import assignment_metrics


def exact_values(graph, layers):
    minima = {}
    for ranks in product(range(layers), repeat=len(graph.nodes)):
        if any(ranks[u] == ranks[v] for u, v in graph.edges):
            continue
        wraps = sum(ranks[u] > ranks[v] for u, v in graph.edges)
        value = sum(((ranks[v] - ranks[u]) % layers) ** 2 for u, v in graph.edges)
        minima[wraps] = min(minima.get(wraps, value), value)
    return minima


def main():
    with use_local_license():
        for seed in range(12):
            rng = Random(seed)
            nodes = tuple(range(5))
            candidates = [(u, v) for u in nodes for v in nodes if u != v]
            graph = Graph(nodes, tuple(rng.sample(candidates, 6)))
            for layers in (3, 4):
                for wraps, expected in sorted(exact_values(graph, layers).items()):
                    result = optimize_square_epigraph(graph, layers, wraps)
                    metrics = assignment_metrics(graph, result, layers, wraps)
                    assert result.solver_status == gp.GRB.OPTIMAL
                    assert metrics["assignment_violations"] == 0
                    assert metrics["span_square_sum"] == expected
                    print(json.dumps({"seed": seed, "layers": layers, "wraps": wraps,
                                      "edges": graph.edges, "objective": expected}))


if __name__ == "__main__":
    main()
