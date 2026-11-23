"""Compare the optimized cyclic DP with exhaustive, direct edge evaluation."""

import copy
from itertools import product
import random

import pytest

from torus_layout.crossing import (
    count_crossings, count_seam_segments, optimize_seam, reduce_crossings,
)
from torus_layout.crossing.seam import _prepare_pair, _transition
from torus_layout.models import CrossingResult, Graph, SubdividedGraph


def _case(seed, layer_count=4):
    rng = random.Random(seed)
    layers = {}
    for i in range(layer_count):
        layers[2 * i] = [f"{i}:{j}" for j in range(rng.randrange(1, 4))]
    keys = list(layers)
    edges = []
    winding = {}
    for i, key in enumerate(keys):
        for u in layers[key]:
            for v in layers[keys[(i + 1) % layer_count]]:
                if rng.random() < 0.6:
                    edge = (u, v) if rng.random() < 0.7 else (v, u)
                    edges.append(edge)
                    winding[edge] = rng.randrange(-2, 3)
    if edges:
        edges.append(edges[0])  # Occurrences must be counted, not deduplicated.
    nodes = tuple(node for group in layers.values() for node in group)
    graph = SubdividedGraph(Graph(nodes, tuple(edges)), layers, {}, {}, nodes)
    return graph, CrossingResult(copy.deepcopy(layers), winding)


def _direct_cost(graph, crossing, gaps):
    shift = {
        node: int(position < gap)
        for nodes, gap in zip(crossing.order.values(), gaps)
        for position, node in enumerate(nodes)
    }
    return sum(
        crossing.winding_numbers.get((u, v), 0) + shift[u] - shift[v] != 0
        for u, v in graph.graph.edges
    )


@pytest.mark.parametrize("layer_count", [2, 3, 4, 5])
@pytest.mark.parametrize("seed", range(15))
def test_dp_matches_exhaustive_search_and_preserves_embedding(seed, layer_count):
    graph, crossing = _case(seed, layer_count)
    before = copy.deepcopy((graph, crossing))
    expected = min(
        _direct_cost(graph, crossing, gaps)
        for gaps in product(*(range(len(nodes)) for nodes in crossing.order.values()))
    )
    actual = optimize_seam(graph, crossing)
    assert count_seam_segments(graph, actual) == expected
    assert count_crossings(graph, actual) == count_crossings(graph, crossing)
    assert (graph, crossing) == before
    for key, nodes in crossing.order.items():
        assert any(actual.order[key] == nodes[i:] + nodes[:i] for i in range(len(nodes)))
    assert optimize_seam(graph, crossing) == actual  # Deterministic ties.


@pytest.mark.parametrize("seed", range(15))
def test_range_updates_match_direct_min_plus(seed):
    rng = random.Random(seed)
    n, k = rng.randrange(1, 12), rng.randrange(1, 12)
    edges = [(rng.randrange(n), rng.randrange(k), rng.randrange(-3, 4)) for _ in range(40)]
    pair = _prepare_pair(n, k, edges)
    values = [rng.randrange(20) for _ in range(n)]
    actual, parents = _transition(values, pair)
    for b in range(k):
        candidates = [
            values[a] + sum(z + int(a > p) - int(b > q) != 0 for p, q, z in edges)
            for a in range(n)
        ]
        assert actual[b] == min(candidates)
        assert parents[b] == candidates.index(min(candidates))


def test_empty_layers_and_no_edges():
    graph, crossing = _case(4)
    empty = SubdividedGraph(Graph(graph.graph.nodes, ()), graph.layers, {}, {}, graph.original_nodes)
    assert optimize_seam(empty, crossing) is crossing
    graph = SubdividedGraph(Graph(("a", "b"), ()), {0: ["a"], 1: [], 2: ["b"]}, {}, {}, ("a", "b"))
    assert reduce_crossings(graph).order == {0: ["a"], 1: [], 2: ["b"]}


def test_nonadjacent_edges_rejected():
    layers = {i: [i] for i in range(4)}
    graph = SubdividedGraph(Graph(tuple(range(4)), ((0, 2),)), layers, {}, {}, tuple(range(4)))
    with pytest.raises(ValueError, match="adjacent"):
        optimize_seam(graph, CrossingResult(layers, {}))


def test_radial_crossing_integration_reduces_seams():
    # Search a reproducible set of proper graphs, rather than an artificial DP table.
    reductions = 0
    for seed in range(15):
        graph, _ = _case(seed)
        baseline = reduce_crossings(graph, rounds=1, optimize_seams=False, sifting_method="radial")
        optimized = reduce_crossings(graph, rounds=1, sifting_method="radial")
        assert count_seam_segments(graph, optimized) <= count_seam_segments(graph, baseline)
        assert count_crossings(graph, optimized) == count_crossings(graph, baseline)
        reductions += count_seam_segments(graph, optimized) < count_seam_segments(graph, baseline)
    assert reductions > 0
