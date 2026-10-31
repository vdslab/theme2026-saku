import copy
import pytest
from torus_layout import Graph
from torus_layout.models import LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from lib.insert_dummy_node import insert_dummy_node as legacy

CASES = [
    ((0, 1, 2), ((0, 2), (2, 0)), {0: [0], 1: [1], 2: [2]}, {(2, 0): True}),
    (("a", "b"), (("a", "b"), ("a", "b")), {0: ["a"], 1: [], 2: ["b"]}, {}),
    ((0, 1), ((0, 1), (1, 0)), {2: [0], 7: [1]}, {(1, 0): True}),
    ((0, 1), ((0, 1),), {0: [0]}, {}),
    ((), (), {}, {}),
    ((0, 1), ((0, 1),), {0: [0], 1: [0], 2: [1]}, {}),
]


@pytest.mark.parametrize("nodes,edges,layers,flags", CASES)
def test_subdivision_matches_legacy(nodes, edges, layers, flags):
    original = copy.deepcopy((nodes, edges, layers, flags))
    weights = {edge: 2.5 for edge in edges}
    expected = legacy(list(nodes), list(edges), layers, flags, weights)
    assignment = LayerAssignmentResult(
        {n: k for k, vs in layers.items() for n in vs}, flags, 0
    )
    actual = insert_dummy_nodes(
        Graph(nodes, edges), assignment, layers=layers, w=weights
    )
    assert (
        list(actual.graph.nodes),
        list(actual.graph.edges),
        actual.layers,
        actual.torus_flags,
        actual.weights,
    ) == expected
    assert actual.original_nodes == nodes
    assert (nodes, edges, layers, flags) == original


def test_layer_index_avoids_repeated_membership_scans():
    class CountingList(list):
        membership_calls = 0

        def __contains__(self, item):
            type(self).membership_calls += 1
            return super().__contains__(item)

    nodes = tuple(range(300))
    layers = {
        layer: CountingList(range(layer * 10, (layer + 1) * 10)) for layer in range(30)
    }
    edges = tuple((node, ((node // 10 + 1) % 30) * 10) for node in nodes)
    expected = legacy(list(nodes), list(edges), layers)
    assert CountingList.membership_calls == 2 * len(edges) * len(layers)
    CountingList.membership_calls = 0
    graph = Graph(nodes, edges)
    assignment = LayerAssignmentResult(
        {n: k for k, ns in layers.items() for n in ns}, {}, 0
    )
    actual = insert_dummy_nodes(graph, assignment, layers=layers)
    assert CountingList.membership_calls == 0
    assert (
        list(actual.graph.nodes),
        list(actual.graph.edges),
        actual.layers,
        actual.torus_flags,
        actual.weights,
    ) == expected
