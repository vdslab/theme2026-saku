import copy

import pytest

from torus_layout.coordinates import assign_coordinates
from torus_layout.coordinates.replicated import expand_3x3
from torus_layout.drawing.preparation import prepare_drawing
from torus_layout.models import CrossingResult, Graph, SubdividedGraph


def seam_chain(winding=1):
    edges = (("a", "b"), ("b", "c"), ("c", "d"))
    order = {0: ["b"], 1: ["c"], 2: ["d", "a"]}
    graph = SubdividedGraph(
        Graph(("a", "b", "c", "d"), edges), order,
        {("a", "b"): True}, {edge: 1.0 for edge in edges}, ("a", "d"),
    )
    return graph, CrossingResult(order, {("a", "b"): winding})


def test_lifts_both_seams_and_preserves_proper_layers():
    graph, crossing = seam_chain()
    before = copy.deepcopy((graph, crossing))
    expanded = expand_3x3(graph, crossing)
    ids = expanded.node_ids
    assert len(ids) == 9 * len(graph.graph.nodes)
    assert (ids["a", 0, 0], ids["b", 1, 1]) in expanded.graph.graph.edges
    assert (ids["a", 0, 0], ids["b", 0, 0]) not in expanded.graph.graph.edges
    assert expanded.omitted_segments == 5
    layer_of = {
        node: layer for layer, nodes in expanded.graph.layers.items() for node in nodes
    }
    assert all(layer_of[v] == layer_of[u] + 1 for u, v in expanded.graph.graph.edges)
    assert (graph, crossing) == before


@pytest.mark.parametrize("winding", [-2, -1, 0, 1, 2])
@pytest.mark.parametrize("gap", [0.5, 1.0, 2.0])
def test_central_extraction_fits_drawing_domain(winding, gap):
    graph, crossing = seam_chain(winding)
    result = assign_coordinates(
        graph, crossing, method="brandes_koepf_3x3", min_gap=gap,
    )
    assert set(result.positions) == set(graph.graph.nodes)
    for layer, nodes in graph.layers.items():
        assert all(result.positions[node][0] == layer for node in nodes)
        assert all(
            result.positions[v][1] - result.positions[u][1] >= gap - 1e-9
            for u, v in zip(nodes, nodes[1:])
        )
    prepare_drawing(
        list(graph.original_nodes), list(graph.graph.edges), graph.layers,
        crossing.order, crossing.winding_numbers, graph.torus_flags,
        result.positions, vertical_period=result.period, show=False,
    )


def test_large_winding_is_clipped_without_reconnecting_to_wrong_copy():
    graph, crossing = seam_chain(2)
    expanded = expand_3x3(graph, crossing)
    source = expanded.node_ids["a", 0, 0]
    assert not any(u == source for u, _ in expanded.graph.graph.edges)
    assert (expanded.node_ids["a", 0, -1], expanded.node_ids["b", 1, 1]) in expanded.graph.graph.edges


def test_rejects_fractional_winding():
    graph, crossing = seam_chain(0.5)
    with pytest.raises(ValueError, match="integer winding"):
        expand_3x3(graph, crossing)


def test_empty_graph():
    graph = SubdividedGraph(Graph((), ()), {}, {}, {}, ())
    result = assign_coordinates(graph, CrossingResult({}, {}), method="brandes_koepf_3x3")
    assert result.positions == {}
    assert result.period == 1.0
