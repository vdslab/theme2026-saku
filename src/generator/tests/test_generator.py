"""追加パッケージの互換性、生成グラフの性質、統一入口を検証する。"""

import random

import networkx as nx
import pytest

from generator import (
    generate_cyclic_graph,
    generate_dag,
    generate_graph,
    generate_mixed_graph,
    generate_random_connected_graph,
    generate_watts_strogatz_graph,
)
from generator.lib.connectivity import is_connected
from lib import generate_torus_graph as legacy

GENERATORS = [
    ("random", generate_random_connected_graph, legacy.generate_random_connected_graph),
    ("dag", generate_dag, legacy.generate_dag),
    ("cyclic", generate_cyclic_graph, legacy.generate_cyclic_graph),
    ("mixed", generate_mixed_graph, legacy.generate_mixed_graph),
    (
        "watts_strogatz",
        generate_watts_strogatz_graph,
        legacy.generate_watts_strogatz_graph,
    ),
]


@pytest.mark.parametrize("graph_type,new_generator,old_generator", GENERATORS)
@pytest.mark.parametrize("n", [8, 12, 20])
@pytest.mark.parametrize("seed", [0, 1, 42])
def test_seeded_results_match_legacy(
    graph_type, new_generator, old_generator, n, seed
):
    state = random.getstate()
    try:
        expected = old_generator(n, seed=seed)
    finally:
        random.setstate(state)

    assert new_generator(n, seed=seed) == expected
    assert generate_graph(graph_type, n, seed=seed) == expected


@pytest.mark.parametrize(
    "graph_type,parameters",
    [
        ("random", {"edge_prob": 0}),
        ("dag", {"edge_prob": 0.05}),
        ("cyclic", {"num_cycles": 3, "edge_prob": 0}),
        ("mixed", {"edge_prob": 0.05, "cycle_prob": 0.5}),
        (
            "watts_strogatz",
            {"k": 2, "p": 0.5, "ensure_connected": False, "tries": 5},
        ),
    ],
)
def test_router_forwards_method_specific_parameters(graph_type, parameters):
    old_generator = next(old for name, _, old in GENERATORS if name == graph_type)
    state = random.getstate()
    try:
        expected = old_generator(20, seed=42, **parameters)
    finally:
        random.setstate(state)
    assert generate_graph(graph_type, 20, seed=42, **parameters) == expected


@pytest.mark.parametrize("graph_type", [name for name, _, _ in GENERATORS])
@pytest.mark.parametrize("seed", [None, 42])
def test_returned_seed_reproduces_graph(graph_type, seed):
    vertices, edges, used_seed = generate_graph(
        graph_type, 20, seed=seed, return_seed=True
    )
    assert isinstance(used_seed, int)
    if seed is not None:
        assert used_seed == seed
    assert generate_graph(graph_type, 20, seed=used_seed) == (vertices, edges)


@pytest.mark.parametrize("graph_type,new_generator,old_generator", GENERATORS)
@pytest.mark.parametrize("seed", [None, 42])
def test_generation_preserves_global_random_state(
    graph_type, new_generator, old_generator, seed
):
    state = random.getstate()
    new_generator(20, seed=seed)
    generate_graph(graph_type, 20, seed=seed)
    assert random.getstate() == state


@pytest.mark.parametrize("graph_type", [name for name, _, _ in GENERATORS])
def test_graphs_are_weakly_connected_with_valid_vertices(graph_type):
    vertices, edges = generate_graph(graph_type, 20, seed=42)
    assert vertices == list(range(20))
    assert all(
        source in vertices and target in vertices and source != target
        for source, target in edges
    )
    graph = nx.DiGraph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(edges)
    assert nx.is_weakly_connected(graph)
    assert is_connected(vertices, edges)


@pytest.mark.parametrize("n", [0, 1, 2])
@pytest.mark.parametrize("graph_type", ["random", "dag", "mixed"])
def test_small_graphs(graph_type, n):
    vertices, edges = generate_graph(graph_type, n, seed=42)
    assert vertices == list(range(n))
    assert is_connected(vertices, edges)
    assert all(source in vertices and target in vertices for source, target in edges)


@pytest.mark.parametrize("edge_prob", [0, 0.3, 1])
def test_dag_remains_acyclic_after_connectivity_completion(edge_prob):
    vertices, edges = generate_graph("dag", 20, edge_prob=edge_prob, seed=42)
    graph = nx.DiGraph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(edges)
    assert nx.is_directed_acyclic_graph(graph)
    assert nx.is_weakly_connected(graph)


@pytest.mark.parametrize("n,num_cycles", [(3, 2), (4, 2), (5, 2), (8, 3), (10, 100)])
def test_cyclic_graph_handles_insufficient_vertices(n, num_cycles):
    vertices, edges = generate_graph(
        "cyclic", n, num_cycles=num_cycles, edge_prob=0, seed=42
    )
    assert all(source in vertices and target in vertices for source, target in edges)
    graph = nx.DiGraph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(edges)
    assert nx.is_weakly_connected(graph)
    assert not nx.is_directed_acyclic_graph(graph)


def test_direct_cyclic_seed_can_be_reused():
    vertices, edges, seed = generate_cyclic_graph(20, return_seed=True)
    assert generate_cyclic_graph(20, seed=seed) == (vertices, edges)


def test_unrewired_watts_strogatz_contains_clockwise_cycle():
    vertices, edges = generate_graph("watts_strogatz", 10, k=2, p=0, seed=42)
    assert len(edges) == 10
    assert {(vertex, (vertex + 1) % 10) for vertex in vertices}.issubset(edges)


def test_connectivity_ignores_edge_direction():
    assert is_connected([10, 20, 30], [(20, 10), (30, 20)])
    assert not is_connected([10, 20, 30], [(20, 10)])
    assert is_connected([], [])


def test_router_rejects_unknown_method():
    with pytest.raises(ValueError, match="unknown graph_type"):
        generate_graph("unknown", 20)


def test_router_rejects_parameters_from_other_methods():
    with pytest.raises(TypeError, match="num_cycles"):
        generate_graph("dag", 20, num_cycles=2)


@pytest.mark.parametrize("graph_type", [name for name, _, _ in GENERATORS])
@pytest.mark.parametrize("n", [-1, 3.5, True])
def test_invalid_node_counts(graph_type, n):
    with pytest.raises(ValueError, match="n must be an integer"):
        generate_graph(graph_type, n)


@pytest.mark.parametrize(
    "graph_type,parameters",
    [
        ("random", {"edge_prob": -0.1}),
        ("dag", {"edge_prob": 1.1}),
        ("cyclic", {"edge_prob": float("nan")}),
        ("mixed", {"cycle_prob": -0.1}),
        ("mixed", {"edge_prob": 1.1}),
        ("watts_strogatz", {"p": 1.1}),
        ("cyclic", {"num_cycles": 0}),
        ("cyclic", {"num_cycles": 1.5}),
        ("watts_strogatz", {"k": 3}),
        ("watts_strogatz", {"k": 20}),
        ("watts_strogatz", {"tries": 0}),
    ],
)
def test_invalid_method_parameters(graph_type, parameters):
    with pytest.raises(ValueError):
        generate_graph(graph_type, 20, **parameters)


@pytest.mark.parametrize("graph_type", ["cyclic", "watts_strogatz"])
def test_methods_requiring_cycles_reject_fewer_than_three_vertices(graph_type):
    with pytest.raises(ValueError, match="n must be an integer at least 3"):
        generate_graph(graph_type, 2)
