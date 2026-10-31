from torus_layout import Graph
from torus_layout.models import LayerAssignmentResult

def test_graph_keeps_order_and_duplicates():
    graph = Graph(("b", "a"), (("b", "a"), ("b", "a")))
    assert graph.nodes == ("b", "a")
    assert len(graph.edges) == 2

def test_layers_follow_assignment_order_and_are_independent():
    result = LayerAssignmentResult({"b": 2, "a": 0, "c": 2}, {}, 0)
    layers = result.layers
    assert list(layers) == [2, 0]
    assert layers[2] == ["b", "c"]
    layers[2].clear()
    assert result.layers[2] == ["b", "c"]
