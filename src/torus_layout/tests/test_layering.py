import pytest
from torus_layout import Graph
from torus_layout.layering import (
    balance_diff,
    balance_layers,
    find_minimum_configuration,
)
from torus_layout.layering.balance import diff, diff_square, qp
from torus_layout.layering import minimize_wraps
from old_torus_layout.layer_assignment import (
    torus_balance as old_balance,
    torus_two_stage as old_min,
    torus_binary_search as old_search,
)

CASES = [
    (tuple(range(4)), ((0, 1), (1, 2), (2, 3))),
    (tuple(range(3)), ((0, 1), (1, 2), (2, 0))),
    (("a", "b", "c"), (("a", "b"), ("b", "c"))),
]


@pytest.mark.parametrize("nodes,edges", CASES)
def test_search_and_diff_match_legacy(nodes, edges, local_solver, monkeypatch):
    for module in (diff, minimize_wraps, old_balance, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    graph = Graph(nodes, edges)
    expected = old_search.find_minimum_torus_configuration(list(nodes), list(edges))
    actual = find_minimum_configuration(graph)
    assert (actual.layer_count, actual.torus_count) == expected[:2]
    old = old_balance.balance_layer_assignment(
        list(nodes), list(edges), expected[1], expected[0], "diff"
    )
    new = balance_diff(graph, expected[1], expected[0])
    assert (new.node_to_layer, new.torus_flags, new.layers) == old[:3]
    assert graph.nodes == nodes and graph.edges == edges


@pytest.mark.parametrize("method", ["diff", "diff_square", "qp", "barycenter"])
@pytest.mark.parametrize("nodes,edges", CASES)
def test_all_balance_methods_match_legacy(
    method, nodes, edges, local_solver, monkeypatch
):
    for module in (diff, diff_square, qp, minimize_wraps, old_balance, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    n = len(nodes)
    target = old_min.minimize_torus_edges(list(nodes), list(edges), n)[4]
    old = old_balance.balance_layer_assignment(
        list(nodes), list(edges), target, n, method
    )
    new = balance_layers(Graph(nodes, edges), target, n, method)
    assert (new.node_to_layer, new.torus_flags, new.layers) == old[:3]


def test_known_qp_rounding_behavior_is_preserved(local_solver, monkeypatch):
    for module in (qp, old_balance):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    edges = (
        (0, 1),
        (0, 5),
        (0, 6),
        (1, 11),
        (2, 5),
        (4, 2),
        (5, 2),
        (6, 0),
        (6, 3),
        (6, 4),
        (6, 9),
        (7, 8),
        (8, 7),
        (10, 8),
        (11, 10),
    )
    graph = Graph(tuple(range(12)), edges)
    old = old_balance.balance_layer_assignment(
        list(graph.nodes), list(edges), 3, 4, "qp"
    )
    new = balance_layers(graph, 3, 4, "qp")
    assert new.node_to_layer == old[0]
    assert new.torus_flags == old[1]


@pytest.mark.parametrize("method", ["diff", "diff_square", "qp", "barycenter"])
def test_weighted_minimum_spans_match_legacy(method, local_solver, monkeypatch):
    for module in (diff, diff_square, qp, old_balance):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    graph = Graph((0, 1, 2), ((0, 1), (1, 2)))
    weights = {(0, 1): 2.0, (1, 2): 0.5}
    spans = {(0, 1): 2, (1, 2): 1}
    old = old_balance.balance_layer_assignment(
        list(graph.nodes), list(graph.edges), 0, 5, method, weights, spans
    )
    new = balance_layers(graph, 0, 5, method, w=weights, lam=spans)
    assert (new.node_to_layer, new.torus_flags, new.layers) == old[:3]


def test_infeasible_solution_keeps_empty_result(local_solver, monkeypatch):
    for module in (diff, old_balance, minimize_wraps, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    graph = Graph((0, 1), ((0, 1),))
    old = old_balance.balance_layer_assignment(
        list(graph.nodes), list(graph.edges), 0, 1, "diff"
    )
    new = balance_layers(graph, 0, 1, "diff")
    assert (new.node_to_layer, new.torus_flags, new.layers) == old[:3]
    assert (
        minimize_wraps.minimize_torus_edges(list(graph.nodes), list(graph.edges), 1)[4]
        is None
    )


@pytest.mark.parametrize("threshold", [1, 3, 4, 6])
def test_binary_search_keeps_query_sequence(threshold, monkeypatch):
    from torus_layout.layering import search

    queries = []

    def solve(nodes, edges, layers, w=None, lam=None):
        queries.append(layers)
        count = 1 if layers >= threshold else 2
        return {}, {}, {}, 0.0, count

    monkeypatch.setattr(old_search, "minimize_torus_edges", solve)
    expected = old_search.find_minimum_torus_configuration(list(range(6)), [])
    old_queries = list(queries)
    queries.clear()
    monkeypatch.setattr(search, "minimize_torus_edges", solve)
    actual = search.find_minimum_configuration(Graph(tuple(range(6)), ()))
    assert (actual.layer_count, actual.torus_count) == expected[:2]
    assert queries == old_queries
