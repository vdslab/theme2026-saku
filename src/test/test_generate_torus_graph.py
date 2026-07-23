import networkx as nx
import pytest

from lib.generate_torus_graph import generate_watts_strogatz_graph


def test_watts_strogatz_graph_has_expected_size_and_is_connected():
    vertices, edges = generate_watts_strogatz_graph(
        n=20,
        k=4,
        p=0.2,
        seed=42,
    )

    graph = nx.DiGraph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(edges)

    assert len(vertices) == 20
    assert len(edges) == 20 * 4 // 2
    assert nx.is_weakly_connected(graph)


def test_watts_strogatz_graph_is_reproducible():
    first = generate_watts_strogatz_graph(n=20, k=4, p=0.5, seed=42)
    second = generate_watts_strogatz_graph(n=20, k=4, p=0.5, seed=42)

    assert first == second


def test_unrewired_watts_strogatz_graph_contains_clockwise_cycle():
    vertices, edges = generate_watts_strogatz_graph(n=10, k=2, p=0, seed=42)

    expected_cycle = {(i, (i + 1) % len(vertices)) for i in vertices}

    assert expected_cycle.issubset(set(edges))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n": 2}, "n must be at least 3"),
        ({"n": 10, "k": 3}, "k must be a positive even integer"),
        ({"n": 10, "p": 1.1}, "p must be between 0 and 1"),
        ({"n": 10, "tries": 0}, "tries must be positive"),
    ],
)
def test_watts_strogatz_graph_rejects_invalid_parameters(kwargs, message):
    with pytest.raises(ValueError, match=message):
        generate_watts_strogatz_graph(**kwargs)
