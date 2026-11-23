import copy
import random
import pytest
from torus_layout import Graph
from torus_layout.models import LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import reduce_crossings, count_crossings
from old_torus_layout.crossing_reduction.radial import (
    radial_sifting_global_guard_heuristic,
    count_radial_crossings,
)


@pytest.mark.parametrize("rounds", [0, 1, 2])
@pytest.mark.parametrize("seed", range(5))
def test_crossing_matches_legacy(seed, rounds):
    rng = random.Random(seed)
    nodes = tuple(range(12))
    ranks = {node: node // 4 for node in nodes}
    edges = tuple(
        (u, v)
        for u in nodes
        for v in nodes
        if ranks[u] != ranks[v] and rng.random() < 0.18
    )
    flags = {edge: ranks[edge[0]] > ranks[edge[1]] for edge in edges}
    assignment = LayerAssignmentResult(ranks, flags, 0)
    divided = insert_dummy_nodes(Graph(nodes, edges), assignment)
    before = copy.deepcopy(divided)
    expected = radial_sifting_global_guard_heuristic(
        list(nodes), list(edges), assignment.layers, flags, rounds
    )
    actual = reduce_crossings(divided, rounds, optimize_seams=False, unwind=False, sifting_method="parting", algo2=True)
    assert actual.order == expected[0]
    assert actual.winding_numbers == expected[4]
    assert divided.layers == expected[1]
    assert list(divided.graph.edges) == expected[2]
    assert divided.torus_flags == expected[3]
    assert count_crossings(divided, actual) == count_radial_crossings(
        expected[0], expected[4], expected[1], expected[2]
    )
    assert divided == before


@pytest.mark.parametrize(
    "layers", [{0: ["a"], 1: [], 2: ["b"]}, {2: ["a"], 5: ["b"]}, {0: ["a", "b"]}]
)
def test_sparse_or_single_layers_match_legacy(layers):
    nodes = ("a", "b")
    edges = (("a", "b"), ("a", "b"), ("b", "a"))
    assignment = LayerAssignmentResult(
        {n: k for k, ns in layers.items() for n in ns}, {("b", "a"): True}, 0
    )
    divided = insert_dummy_nodes(Graph(nodes, edges), assignment, layers=layers)
    expected = radial_sifting_global_guard_heuristic(
        list(nodes), list(edges), layers, assignment.torus_flags, 1
    )
    actual = reduce_crossings(divided, 1, optimize_seams=False, unwind=False, sifting_method="parting", algo2=True)
    assert (actual.order, actual.winding_numbers) == (expected[0], expected[4])


def test_shortest_sifting_recomputes_windings_after_moving_a_vertex():
    from radial_layout.crossing_reduction import assign_winding_numbers
    from torus_layout.crossing.shortest import sift_with_shortest_windings
    from torus_layout.crossing.lib.crossings import count_all_crossings

    order = {0: [0, 1, 2], 1: [4, 3, 5]}
    edges = [(0, 3), (1, 4), (2, 5)]
    initial = assign_winding_numbers(order, edges)
    assert count_all_crossings(order, initial, [0, 1], edges) == 1

    winding = sift_with_shortest_windings(order, [0, 1], edges, 1)

    assert count_all_crossings(order, winding, [0, 1], edges) == 0
    assert winding == assign_winding_numbers(order, edges)


def test_shortest_sifting_scores_the_two_directed_strips_separately():
    from torus_layout.crossing.shortest import sift_with_shortest_windings
    from torus_layout.crossing.lib.crossings import count_all_crossings

    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3), (2, 1)]

    winding = sift_with_shortest_windings(order, [0, 1], edges, 1)

    assert order == {0: [0, 1], 1: [2, 3]}
    assert winding == dict.fromkeys(edges, 0)  # Radial also uses zero for a half-turn tie.
    assert count_all_crossings(order, winding, [0, 1], edges) == 0


def test_parting_keeps_its_two_layer_result_with_cached_counts():
    from torus_layout.crossing import sifting

    order = {0: [0, 1, 2], 1: [3, 4, 5]}
    edges = [(0, 5), (1, 3), (2, 4), (3, 2), (4, 1)]
    winding = dict.fromkeys(edges, 0)

    sifting.run_sifting_with_global_guard(order, winding, [0, 1], edges, 5)

    assert order == {0: [0, 1, 2], 1: [4, 3, 5]}
    assert winding == dict(zip(edges, (0, 0, 1, -1, -1)))


def test_radial_sifting_uses_each_directed_strip_without_a_global_guard(monkeypatch):
    from torus_layout.crossing import sifting

    order = {0: [0, 1], 1: [2, 3]}
    edges = [(0, 3), (2, 1)]
    winding = dict.fromkeys(edges, 0)
    original = sifting.sift_two_layer_pair
    strips = []

    def record_strip(fixed, free, order, winding, segments, **kwargs):
        strips.append((fixed, free, segments))
        return original(fixed, free, order, winding, segments, **kwargs)

    original_count = sifting.pair_crossings

    def count_strip(order, winding, fixed, free, segments, **kwargs):
        assert len(segments) == 1
        return original_count(order, winding, fixed, free, segments, **kwargs)

    monkeypatch.setattr(sifting, "sift_two_layer_pair", record_strip)
    monkeypatch.setattr(sifting, "pair_crossings", count_strip)
    sifting.run_radial_sifting(order, winding, [0, 1], edges, 2)

    assert strips == [(0, 1, [(0, 3)])] * 2 + [(1, 0, [(2, 1)])] * 2


def test_radial_sifting_retains_the_current_order_and_winding_on_a_tie():
    from torus_layout.crossing.sifting import run_radial_sifting

    order = {0: [0], 1: [1, 2]}
    winding = {(0, 2): 0}

    run_radial_sifting(order, winding, [0, 1], [(0, 2)], 1)

    assert order[1] == [1, 2]
    assert winding[0, 2] == 0


def test_radial_sifting_prefers_fewer_type2_conflicts_over_fewer_crossings():
    from torus_layout.crossing.lib.crossings import count_layer_pair_crossings
    from torus_layout.crossing.lib.embedding import compute_winding_numbers
    from torus_layout.crossing.sifting import run_radial_sifting

    layers = [0, 1]
    inner = [(0, 5), (1, 4)]
    edges = [*inner, (2, 5), (2, 7), (3, 4)]
    for dummy_nodes, expected in ((set(), (1, 1)), ({0, 1, 4, 5}, (2, 0))):
        order = {0: [0, 1, 2, 3], 1: [4, 5, 6, 7]}
        winding = compute_winding_numbers(edges, order, order, layers)
        run_radial_sifting(order, winding, layers, edges, 1, dummy_nodes=dummy_nodes)

        assert (
            count_layer_pair_crossings(order, winding, 0, 1, edges),
            count_layer_pair_crossings(order, winding, 0, 1, inner),
        ) == expected


def test_type2_weight_only_applies_when_both_segments_are_internal():
    from torus_layout.crossing.lib.crossings import sifting_edge_weights, weighted_edge_crossings

    inner1, inner2, outer = (0, 5, 0), (1, 4, 1), (2, 3, 2)
    edges = [inner1, inner2, outer]
    weights = sifting_edge_weights(edges, {0, 1, 4, 5}, len(edges), type2_only=True)
    source = {0: 0, 1: 1, 2: 2}
    target = {3: 0, 4: 1, 5: 2}

    assert weighted_edge_crossings(inner1, inner2, source, target, {}, weights) == 3
    assert weighted_edge_crossings(inner1, outer, source, target, {}, weights) == 1
