"""Contracts shared by layouts, and deliberate differences between them."""


import networkx as nx
import pytest

from layout_common.cycle_removal import remove_cycles
from layout_common.dag import topological_adjacency
from layout_common.hierarchy import insert_dummy_nodes
from radial_layout import assign_layers as radial_layers
from sugiyama_layout import assign_layers as planar_layers


def test_compatibility_exports_share_implementations():
    import radial_layout as radial
    import sugiyama_layout as planar

    for name in ("remove_cycles", "CycleRemovalResult", "insert_dummy_nodes",
                 "DummyNode", "ProperHierarchy", "generate_watts_strogatz_digraph"):
        assert getattr(radial, name) is getattr(planar, name)
    assert radial.assign_layers is not planar.assign_layers
    assert radial.assign_coordinates is not planar.assign_coordinates


def test_cycle_removal_preserves_original_edge_directions_as_metadata():
    nodes = ("a", "b", "c", "isolated")
    edges = (("a", "b"), ("b", "c"), ("c", "a"), ("a", "b"))
    result = remove_cycles(iter(nodes), iter(edges))
    assert result.nodes == nodes
    assert nx.is_directed_acyclic_graph(nx.DiGraph(result.edges))
    assert result.edges == tuple(
        (v, u) if (u, v) in result.reversed_edges else (u, v)
        for u, v in dict.fromkeys(edges)
    )
    assert len(result.reversed_edges) == 1


@pytest.mark.parametrize("edges", [((0, 0),), ((0, 2),)])
def test_cycle_removal_rejects_invalid_input(edges):
    with pytest.raises(ValueError):
        remove_cycles((0, 1), edges)


def test_dag_traversal_keeps_duplicate_edges_and_stable_order():
    order, successors, predecessors = topological_adjacency(
        iter(("b", "a", "c", "b")), iter((("a", "c"), ("a", "c")))
    )
    assert order == ["b", "a", "c"]
    assert successors["a"] == ["c", "c"]
    assert predecessors["c"] == ["a", "a"]


@pytest.mark.parametrize("assign", [planar_layers, radial_layers])
def test_layering_rejects_cycles_and_unknown_endpoints(assign):
    for edges in (((0, 1), (1, 0)), ((0, 2),)):
        with pytest.raises(ValueError):
            assign((0, 1), edges)
    assert assign((), ()) == {}


def test_radial_aligns_sinks_while_planar_uses_source_distances():
    nodes = (0, 1, 2, 3, 4)
    edges = ((0, 1), (1, 2), (0, 3))
    assert planar_layers(nodes, edges) == {0: 0, 4: 0, 1: 1, 3: 1, 2: 2}
    assert radial_layers(nodes, edges) == {0: 0, 1: 1, 2: 2, 3: 2, 4: 2}


def test_shared_subdivision_keeps_chains_and_intermediate_empty_layers():
    hierarchy = insert_dummy_nodes(("a", "b"), (("a", "b"),), {"a": 0, "b": 3})
    chain = hierarchy.chains[("a", "b")]
    assert chain[0] == "a" and chain[-1] == "b"
    assert len(hierarchy.dummy_nodes) == 2
    assert hierarchy.edges == tuple(zip(chain, chain[1:]))
    assert list(hierarchy.layers) == [0, 1, 2, 3]
    with pytest.raises(ValueError):
        insert_dummy_nodes((0, 1), ((0, 1),), {0: 1, 1: 0})


def test_graph_generators_keep_distinct_orientation_policies():
    from generator.random_oriented_watts_strogatz import generate_watts_strogatz_digraph
    from generator.watts_strogatz import generate_watts_strogatz_graph

    nodes, random_edges = generate_watts_strogatz_digraph(10, 7, rewiring_probability=0)
    torus_nodes, clockwise_edges = generate_watts_strogatz_graph(10, p=0, seed=7)
    assert tuple(torus_nodes) == nodes
    assert {frozenset(e) for e in random_edges} == {frozenset(e) for e in clockwise_edges}
    assert all((v - u) % 10 <= (u - v) % 10 for u, v in clockwise_edges)
    assert set(random_edges) != set(clockwise_edges)
