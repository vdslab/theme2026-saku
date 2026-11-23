"""UNWIND-LEVEL preserves crossings and removes shared integer turns."""

import copy
import random

import pytest

from generator import generate_graph
from torus_layout.crossing import count_crossings, count_seam_segments, reduce_crossings, unwind_levels
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult, SubdividedGraph
from torus_layout.subdivision import insert_dummy_nodes


def screenshot_case():
    nodes, edges, _ = generate_graph(
        "cyclic", 25, seed=3409470963, num_cycles=2, edge_prob=0.005
    )
    order = {
        0: [26, 8, 29], 1: [12, 9, 30], 2: [13, 10, 31],
        3: [14, 11, 32], 4: [15, 25, 24], 5: [16, 0, 33],
        6: [17, 1, 34], 7: [18, 2, 35], 8: [19, 3, 36],
        9: [20, 4, 37], 10: [21, 5], 11: [22, 6, 27], 12: [23, 7, 28],
    }
    ranks = {node: layer for layer, group in order.items() for node in group if node < 25}
    assignment = LayerAssignmentResult(ranks, {e: ranks[e[0]] > ranks[e[1]] for e in edges}, 0)
    graph = insert_dummy_nodes(Graph(tuple(nodes), tuple(edges)), assignment)
    winding = {edge: int(edge in {(26, 12), (8, 9), (29, 30)}) for edge in graph.graph.edges}
    return graph, CrossingResult(order, winding)


def test_screenshot_three_unnecessary_wraps_are_removed():
    graph, crossing = screenshot_case()
    before = copy.deepcopy((graph, crossing))
    result = unwind_levels(graph, crossing)
    assert count_crossings(graph, crossing) == count_crossings(graph, result) == 0
    assert count_seam_segments(graph, crossing) == 3
    assert count_seam_segments(graph, result) == 0
    assert result.order == crossing.order
    assert (graph, crossing) == before


def test_global_pipeline_applies_unwind_only_when_requested(monkeypatch):
    from torus_layout.crossing import api

    graph, _ = screenshot_case()
    calls = []

    def observe_unwind(*args, **kwargs):
        calls.append(True)
        return unwind_levels(*args, **kwargs)

    monkeypatch.setattr(api, "unwind_levels", observe_unwind)
    reduce_crossings(graph, sifting_method="global")
    assert not calls
    reduce_crossings(graph, unwind=True, sifting_method="global")
    assert calls


def test_parting_pipeline_unwinds_before_seam_selection(monkeypatch):
    from torus_layout.crossing import api

    graph, _ = screenshot_case()
    baseline = reduce_crossings(graph, rounds=5, unwind=False, sifting_method="parting", algo2=True)
    assert count_seam_segments(graph, baseline) == 3
    original_dp = api.optimize_seam
    calls = []

    def check_dp_input(graph, crossing, *, prioritize_internal=False):
        assert count_seam_segments(graph, crossing) == 0
        calls.append(True)
        return original_dp(graph, crossing, prioritize_internal=prioritize_internal)

    monkeypatch.setattr(api, "optimize_seam", check_dp_input)
    result = reduce_crossings(graph, rounds=5, unwind=True, sifting_method="parting", algo2=True)
    assert calls == [True]
    assert count_seam_segments(graph, result) == 0
    assert count_crossings(graph, result) == count_crossings(graph, baseline) == 0


@pytest.mark.parametrize("minimum", [-2, 2])
def test_two_layer_reverse_edges_and_duplicates_are_updated_once(minimum):
    layers = {10: [0, 2], 30: [1, 3]}
    edges = ((2, 3), (2, 3), (3, 2), (0, 1))
    graph = SubdividedGraph(Graph((0, 1, 2, 3), edges), layers, {}, {}, (0, 1))
    crossing = CrossingResult(layers, {(2, 3): minimum, (3, 2): -minimum, (0, 1): 1})
    result = unwind_levels(graph, crossing)
    assert result.winding_numbers == {(2, 3): 0, (3, 2): 0, (0, 1): 1 - minimum}
    assert count_crossings(graph, result) == count_crossings(graph, crossing)
    assert graph.graph.edges == edges


def test_pair_without_inner_segments_uses_all_segments():
    layers = {0: [0, 2], 1: [1, 3]}
    edges = ((0, 1), (0, 3), (2, 1))
    graph = SubdividedGraph(Graph((0, 1, 2, 3), edges), layers, {}, {}, (0, 1))
    crossing = CrossingResult(layers, {e: 2 for e in edges})
    result = unwind_levels(graph, crossing)
    assert all(value == 0 for value in result.winding_numbers.values())
    assert count_crossings(graph, result) == count_crossings(graph, crossing)


def test_ten_and_eleven_closing_edges_do_not_need_three_turns():
    layers = {0: [12], 20: [10], 21: [11, 52]}
    edges = ((10, 11), (10, 52), (52, 12), (11, 12))
    graph = SubdividedGraph(
        Graph((10, 11, 12, 52), edges), layers,
        {(52, 12): True, (11, 12): True}, {}, (10, 11, 12),
    )
    crossing = CrossingResult(layers, {(10, 11): 0, (10, 52): 0, (52, 12): 3, (11, 12): 3})
    before = copy.deepcopy((graph, crossing))
    result = unwind_levels(graph, crossing)
    assert result.winding_numbers[52, 12] == result.winding_numbers[11, 12] == 0
    assert count_crossings(graph, result) == count_crossings(graph, crossing) == 0
    assert count_seam_segments(graph, crossing) == 2
    assert count_seam_segments(graph, result) == 0
    assert result.order == crossing.order
    assert (graph, crossing) == before


def test_full_ws_case_removes_ten_and_eleven_wraps_after_seam_selection():
    nodes, edges, _ = generate_graph("watts_strogatz", 25, seed=1392931424, k=4, p=0.1)
    originals_by_layer = [
        [12], [13], [14], [15], [16], [17], [18, 19], [20], [21], [22, 23],
        [24], [0], [1], [2], [3], [4, 5], [6], [7], [8], [9], [10], [11],
    ]
    ranks = {node: layer for layer, members in enumerate(originals_by_layer) for node in members}
    ranks = {node: ranks[node] for node in nodes}
    assignment = LayerAssignmentResult(ranks, {e: ranks[e[0]] > ranks[e[1]] for e in edges}, 0)
    graph = insert_dummy_nodes(Graph(tuple(nodes), tuple(edges)), assignment)
    baseline = reduce_crossings(graph, rounds=5, unwind=False, sifting_method="parting", algo2=True)
    result = reduce_crossings(graph, rounds=5, unwind=True, sifting_method="parting", algo2=True)
    assert baseline.winding_numbers[52, 12] == baseline.winding_numbers[11, 12] == 3
    assert result.winding_numbers[10, 52] == 0
    assert result.winding_numbers[52, 12] == result.winding_numbers[11, 12] == 0
    assert count_crossings(graph, baseline) == count_crossings(graph, result) == 2
    assert count_seam_segments(graph, baseline) == 8
    assert count_seam_segments(graph, result) == 3


def test_inner_minimum_zero_takes_precedence_over_all_edge_minimum():
    layers = {0: [0, 2], 1: [1, 3]}
    edges = ((0, 1), (2, 3))
    graph = SubdividedGraph(Graph((0, 1, 2, 3), edges), layers, {}, {}, (0, 1))
    crossing = CrossingResult(layers, {(0, 1): -2, (2, 3): 0})
    assert unwind_levels(graph, crossing) is crossing


def test_fallback_does_not_create_more_wraps_from_a_negative_outlier():
    layers = {0: [0, 2, 4], 1: [1, 3, 5]}
    edges = ((0, 1), (2, 3), (4, 5))
    graph = SubdividedGraph(Graph(tuple(range(6)), edges), layers, {}, {}, tuple(range(6)))
    crossing = CrossingResult(layers, {(0, 1): -3, (2, 3): 0, (4, 5): 0})
    assert unwind_levels(graph, crossing) is crossing


def test_fallback_counts_duplicate_occurrences_when_choosing_shift():
    layers = {0: [0, 2, 4], 1: [1, 3, 5]}
    edges = ((0, 1), (0, 1), (0, 1), (2, 3), (4, 5))
    graph = SubdividedGraph(Graph(tuple(range(6)), edges), layers, {}, {}, tuple(range(6)))
    crossing = CrossingResult(layers, {(0, 1): -2, (2, 3): 0, (4, 5): 0})
    result = unwind_levels(graph, crossing)
    assert result.winding_numbers == {(0, 1): 0, (2, 3): 2, (4, 5): 2}
    assert count_seam_segments(graph, result) == 2
    assert count_crossings(graph, result) == count_crossings(graph, crossing)


@pytest.mark.parametrize("minimum", [-3, 3])
def test_no_inner_segments_with_reverse_edges_and_duplicates(minimum):
    layers = {0: [0, 2], 1: [1, 3]}
    edges = ((0, 1), (0, 1), (3, 2))
    graph = SubdividedGraph(Graph((0, 1, 2, 3), edges), layers, {}, {}, (0, 1, 2, 3))
    crossing = CrossingResult(layers, {(0, 1): minimum, (3, 2): -minimum})
    result = unwind_levels(graph, crossing)
    assert result.winding_numbers == {(0, 1): 0, (3, 2): 0}
    assert count_crossings(graph, result) == count_crossings(graph, crossing)


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("layer_count", [2, 3, 5])
@pytest.mark.parametrize("has_inner_segments", [False, True])
def test_random_embeddings_preserve_crossings_and_are_idempotent(seed, layer_count, has_inner_segments):
    rng = random.Random(seed)
    keys = [4 * index + 1 for index in range(layer_count)]
    layers = {key: [3 * index + offset for offset in range(3)] for index, key in enumerate(keys)}
    edges = []
    winding = {}
    for index, key in enumerate(keys):
        for u in layers[key]:
            for v in layers[keys[(index + 1) % layer_count]]:
                if rng.random() < 0.5:
                    edge = (u, v) if rng.random() < 0.7 else (v, u)
                    edges.append(edge)
                    winding[edge] = rng.randrange(-3, 4)
    if edges:
        edges.append(edges[0])
    nodes = tuple(node for group in layers.values() for node in group)
    originals = tuple(layers[key][0] for key in keys) if has_inner_segments else nodes
    graph = SubdividedGraph(Graph(nodes, tuple(edges)), layers, {}, {}, originals)
    crossing = CrossingResult(layers, winding)
    before = copy.deepcopy((graph, crossing))
    result = unwind_levels(graph, crossing)
    assert count_crossings(graph, result) == count_crossings(graph, crossing)
    assert result.order == layers
    assert unwind_levels(graph, result) == result
    assert (graph, crossing) == before
    if not has_inner_segments:
        assert count_seam_segments(graph, result) <= count_seam_segments(graph, crossing)


@pytest.mark.parametrize("layers", [{}, {0: [0]}])
def test_empty_or_single_layer_is_unchanged(layers):
    nodes = tuple(n for group in layers.values() for n in group)
    graph = SubdividedGraph(Graph(nodes, ()), layers, {}, {}, nodes)
    crossing = CrossingResult(layers, {})
    assert unwind_levels(graph, crossing) is crossing


def test_nonadjacent_segments_are_rejected():
    layers = {i: [i] for i in range(4)}
    graph = SubdividedGraph(Graph(tuple(range(4)), ((0, 2),)), layers, {}, {}, ())
    with pytest.raises(ValueError, match="adjacent"):
        unwind_levels(graph, CrossingResult(layers, {(0, 2): 1}))
