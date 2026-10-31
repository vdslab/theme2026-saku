import pytest
from torus_layout import Graph
from torus_layout.layering import balance_diff, find_minimum_configuration
from torus_layout.layering.balance import diff
from torus_layout.layering import minimize_wraps
from layer_assignment import torus_balance as old_balance, torus_two_stage as old_min, torus_binary_search as old_search

CASES = [
    (tuple(range(4)), ((0,1),(1,2),(2,3))),
    (tuple(range(3)), ((0,1),(1,2),(2,0))),
    (("a","b","c"), (("a","b"),("b","c"))),
]

@pytest.mark.parametrize("nodes,edges", CASES)
def test_search_and_diff_match_legacy(nodes, edges, local_solver, monkeypatch):
    for module in (diff, minimize_wraps, old_balance, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    graph = Graph(nodes, edges)
    expected = old_search.find_minimum_torus_configuration(list(nodes),list(edges))
    actual = find_minimum_configuration(graph)
    assert (actual.layer_count,actual.torus_count) == expected[:2]
    old = old_balance.balance_layer_assignment(list(nodes),list(edges),expected[1],expected[0],"diff")
    new = balance_diff(graph,expected[1],expected[0])
    assert (new.node_to_layer,new.torus_flags,new.layers) == old[:3]
    assert graph.nodes == nodes and graph.edges == edges
