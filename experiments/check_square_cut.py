"""Independently enumerate small integer assignments for fixed wrap sets."""

from itertools import product
import json
from random import Random

from torus_layout.models import Graph, LayerAssignmentResult
from torus_study.square_cut import minimize_square_ranks


def main():
    nodes = tuple(range(5))
    for seed, layers in product(range(20), (3, 4)):
        rng = Random(seed)
        initial = {u: rng.randrange(layers) for u in nodes}
        possible = [(u, v) for u, v in product(nodes, repeat=2) if initial[u] != initial[v]]
        edges = tuple(rng.sample(possible, min(7, len(possible))))
        flags = {(u, v): initial[u] > initial[v] for u, v in edges}
        graph = Graph(nodes, edges)

        def spans(ranks):
            return [ranks[v] - ranks[u] + layers * flags[u, v] for u, v in edges]

        candidates = map(spans, product(range(layers), repeat=len(nodes)))
        optimum = min(sum(span * span for span in candidate) for candidate in candidates
                      if all(1 <= span < layers for span in candidate))
        result, iterations = minimize_square_ranks(graph, layers, LayerAssignmentResult(initial, flags, 0))
        scaled, scaled_iterations = minimize_square_ranks(
            graph, layers, LayerAssignmentResult(initial, flags, 0), scaled=True
        )
        assert sum(span * span for span in spans(scaled)) == optimum
        assert all(1 <= span < layers for span in spans(scaled))
        assert all(0 <= rank < layers for rank in scaled.values())
        actual = spans(result)
        assert all(1 <= span < layers for span in actual)
        assert all(0 <= rank < layers for rank in result.values())
        assert sum(span * span for span in actual) == optimum
        print(json.dumps({"seed": seed, "layers": layers, "edges": edges,
                          "optimum": optimum, "iterations": iterations, "scaled_iterations": scaled_iterations}))


if __name__ == "__main__":
    main()
