import copy
import random
import pytest
from torus_layout import Graph
from torus_layout.models import LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import reduce_crossings, count_crossings
from crossing_reduction.radial import (
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
    actual = reduce_crossings(divided, rounds, optimize_seams=False)
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
    actual = reduce_crossings(divided, 1, optimize_seams=False)
    assert (actual.order, actual.winding_numbers) == (expected[0], expected[4])
