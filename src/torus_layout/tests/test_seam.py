"""Compare the optimized cyclic DP with exhaustive, direct edge evaluation."""

import copy
from collections import defaultdict
from itertools import product
import random

import pytest

from torus_layout.crossing import (
    count_crossings, count_seam_segments, optimize_joint_seam, optimize_seam, reduce_crossings,
)
from torus_layout.crossing.api import _process_boundaries
from torus_layout.crossing.seam import _prepare_pair, _transition, seam_score
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult, SubdividedGraph
from torus_layout.subdivision import insert_dummy_nodes


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


def _cut_windings(graph, crossing, gaps):
    # Lift each edge to the covering space. Measure both endpoints in their
    # layer's rank units, with the selected gap as the periodic origin.
    locations = {
        node: (position - gaps[layer], len(nodes))
        for layer, nodes in crossing.order.items()
        for position, node in enumerate(nodes)
    }
    winding = {}
    for u, v in graph.graph.edges:
        source, source_period = locations[u]
        target, target_period = locations[v]
        lifted_target = target + target_period * crossing.winding_numbers.get((u, v), 0)
        winding[u, v] = lifted_target // target_period - source // source_period
    return winding


def _direct_cost(graph, winding, prioritize_internal):
    wrapped = [edge for edge in graph.graph.edges if winding[edge]]
    internal = 0
    if prioritize_internal:
        dummy = graph.dummy_nodes
        internal = sum(u in dummy and v in dummy for u, v in wrapped)
    return internal, len(wrapped)


def _assert_exhaustive_optimum(graph, crossing, actual, prioritize_internal):
    layers = list(crossing.order)
    assert actual.order.keys() == crossing.order.keys()
    candidates = [range(max(1, len(crossing.order[layer]))) for layer in layers]
    actual_gaps = {}
    for layer, gaps in zip(layers, candidates):
        nodes = crossing.order[layer]
        matching = [gap for gap in gaps if actual.order[layer] == nodes[gap:] + nodes[:gap]]
        assert matching, (layer, nodes, actual.order[layer])
        actual_gaps[layer] = matching[0]

    expected = min(
        _direct_cost(graph, _cut_windings(graph, crossing, dict(zip(layers, gaps))), prioritize_internal)
        for gaps in product(*candidates)
    )
    actual_winding = _cut_windings(graph, crossing, actual_gaps)
    assert _direct_cost(graph, actual_winding, prioritize_internal) == expected
    assert all(actual.winding_numbers.get(edge, 0) == value for edge, value in actual_winding.items())
    original_winding = _cut_windings(graph, crossing, dict.fromkeys(layers, 0))
    if expected == _direct_cost(graph, original_winding, prioritize_internal):
        assert actual == crossing
    return expected


@pytest.mark.parametrize("layer_count", range(2, 8))
@pytest.mark.parametrize("seed", range(64))
@pytest.mark.parametrize("prioritize_internal", [False, True])
def test_dp_matches_exhaustive_search_and_preserves_embedding(seed, layer_count, prioritize_internal):
    graph, crossing = _case(seed, layer_count)
    graph = SubdividedGraph(graph.graph, graph.layers, {}, {}, graph.original_nodes[::3])
    crossing = CrossingResult(dict(reversed(list(crossing.order.items()))), crossing.winding_numbers)
    before = copy.deepcopy((graph, crossing))
    actual = optimize_seam(graph, crossing, prioritize_internal=prioritize_internal)
    _assert_exhaustive_optimum(graph, crossing, actual, prioritize_internal)
    assert count_crossings(graph, actual) == count_crossings(graph, crossing)
    assert (graph, crossing) == before
    assert optimize_seam(graph, crossing, prioritize_internal=prioritize_internal) == actual


def test_dp_includes_last_to_first_pair_with_an_empty_layer():
    order = {0: ["a", "b"], 2: [], 4: ["c", "d"], 6: ["e"]}
    edge = ("e", "a")
    nodes = ("a", "b", "c", "d", "e")
    graph = SubdividedGraph(Graph(nodes, (edge,)), order, {}, {}, nodes)
    crossing = CrossingResult(order, {edge: 1})
    actual = optimize_seam(graph, crossing)
    assert _assert_exhaustive_optimum(graph, crossing, actual, False) == (0, 0)
    assert actual.order[0] == ["b", "a"]


def test_a_full_turn_across_two_calls_changes_the_winding():
    order = {0: ["a"], 1: ["b", "c"]}
    nodes = ("a", "b", "c")
    edges = (("a", "b"), ("a", "c"))
    graph = SubdividedGraph(Graph(nodes, edges), order, {}, {}, nodes)
    crossing = CrossingResult(order, dict.fromkeys(edges, 1))
    first = optimize_seam(graph, crossing)
    second = optimize_seam(graph, first)
    assert _assert_exhaustive_optimum(graph, crossing, first, False) == (0, 1)
    assert _assert_exhaustive_optimum(graph, first, second, False) == (0, 0)
    assert second.order == crossing.order


def test_dp_accepts_more_seam_segments_to_eliminate_internal_seam():
    order = {0: ["d1", "a"], 1: ["d2", "b"]}
    edges = (("d1", "d2"), ("d1", "b"), ("d1", "b"), ("a", "d2"), ("a", "d2"))
    graph = SubdividedGraph(Graph(("a", "b", "d1", "d2"), edges), order, {}, {}, ("a", "b"))
    crossing = CrossingResult(order, {("d1", "b"): -1})
    assert seam_score(graph, optimize_seam(graph, crossing), True) == (1, 1)
    weighted = optimize_seam(graph, crossing, prioritize_internal=True)
    assert seam_score(graph, weighted, True) == (0, 2)


@pytest.mark.parametrize("layer_count", [2, 3, 5])
@pytest.mark.parametrize("seed", range(20))
def test_joint_dp_matches_exhaustive_cuts_and_turns(seed, layer_count):
    graph, crossing = _case(seed, layer_count)
    graph = SubdividedGraph(graph.graph, graph.layers, {}, {}, graph.original_nodes[::3])
    before = copy.deepcopy((graph, crossing))
    layers = crossing.order
    layer_of = {node: layer for layer, nodes in layers.items() for node in nodes}
    dummy = graph.dummy_nodes
    best = None
    for cuts in product(*(range(len(nodes)) for nodes in layers.values())):
        winding = _cut_windings(graph, crossing, dict(zip(layers, cuts)))
        strips = defaultdict(list)
        for u, v in graph.graph.edges:
            a, b = layer_of[u], layer_of[v]
            turn = winding[u, v] if a < b else -winding[u, v]
            strips[min(a, b), max(a, b)].append((turn, u in dummy and v in dummy))
        total = 0
        for segments in strips.values():
            choices = {turn for turn, _ in segments}
            costs = [sum(turn != offset for turn, _ in segments) for offset in choices
                     if all(turn == offset for turn, internal in segments if internal)]
            if not costs:
                break
            total += min(costs)
        else:
            best = total if best is None else min(best, total)

    result = optimize_joint_seam(graph, crossing)
    assert (graph, crossing) == before
    if best is None:
        assert result is None
    else:
        assert result is not None
        assert _direct_cost(graph, result.winding_numbers, True) == (0, best)
        assert count_crossings(graph, result) == count_crossings(graph, crossing)


def test_default_joint_boundary_improves_on_legacy_example():
    ranks = dict(enumerate((0, 1, 2, 1, 0)))
    edges = ((0, 1), (1, 2), (2, 0), (0, 3), (3, 0), (2, 4), (4, 2), (3, 2), (4, 3))
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    graph = insert_dummy_nodes(Graph(tuple(ranks), edges), LayerAssignmentResult(ranks, flags, 0))

    result = reduce_crossings(graph, rounds=2)
    legacy = reduce_crossings(graph, rounds=2, seam_method="legacy")
    assert seam_score(graph, result, True) == (0, 1)
    assert seam_score(graph, legacy, True) == (0, 2)
    assert count_crossings(graph, result) == count_crossings(graph, legacy) == 0


def test_infeasible_joint_boundary_reports_legacy_option():
    layers = {0: ["a", "b"], 1: ["c", "d"]}
    edges = (("a", "c"), ("b", "d"))
    graph = SubdividedGraph(Graph(("a", "b", "c", "d"), edges), layers, {}, {}, ())
    crossing = CrossingResult(layers, {edges[0]: 3, edges[1]: 0})
    with pytest.raises(ValueError, match="--seam-method legacy"):
        _process_boundaries(graph, crossing, True, True, True)
    legacy = _process_boundaries(graph, crossing, True, True, True, seam_method="legacy")
    assert seam_score(graph, legacy, True)[0] == 1


@pytest.mark.parametrize("seed", range(15))
def test_range_updates_match_direct_min_plus(seed):
    rng = random.Random(seed)
    n, k = rng.randrange(1, 12), rng.randrange(1, 12)
    edges = [
        (rng.randrange(n), rng.randrange(k), rng.randrange(-3, 4), rng.randrange(1, 50))
        for _ in range(40)
    ]
    pair = _prepare_pair(n, k, edges)
    values = [rng.randrange(20) for _ in range(n)]
    actual, parents = _transition(values, pair)
    for b in range(k):
        candidates = [
            values[a] + sum(weight for p, q, z, weight in edges if z + int(a > p) - int(b > q))
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
        baseline = reduce_crossings(
            graph, rounds=1, unwind=False, optimize_seams=False, sifting_method="radial",
        )
        optimized = reduce_crossings(graph, rounds=1, unwind=False, sifting_method="radial")
        _assert_exhaustive_optimum(graph, baseline, optimized, False)
        assert count_crossings(graph, optimized) == count_crossings(graph, baseline)
        reductions += count_seam_segments(graph, optimized) < count_seam_segments(graph, baseline)
    assert reductions > 0
