from collections import defaultdict

from sugiyama_layout import condense_cycles, count_crossings, reduce_crossings
from sugiyama_layout.coordinate_assignment import _improve_level


def test_two_level_bc_example_from_section_iii_a():
    layers = {0: tuple("abcd"), 1: tuple("efghi")}
    edges = tuple(map(tuple, "ae af be bh bi cf ch ci de dg di".split()))
    assert count_crossings(layers, edges) == 14
    order = reduce_crossings(layers, edges)
    assert order == {0: tuple("dabc"), 1: tuple("geifh")}
    assert count_crossings(order, edges) == 7


def test_isolated_vertices_allow_unoccupied_level_numbers():
    layers = {0: ("a",), 2: ("b",), 4: ("c",)}
    assert reduce_crossings(layers, ()) == layers


def test_n_level_bc_example_from_section_iii_b():
    layers = dict(enumerate(("abc", "def", "ghi", "jkl")))
    edges = tuple(map(tuple, "ae bd cd dg eg eh ei fh gl hj hk".split()))
    assert count_crossings(layers, edges) == 5
    assert count_crossings(reduce_crossings(layers, edges), edges) == 0


def test_priority_layout_example_from_section_iv_b():
    positions = {f"u{i}": i for i in range(1, 10)}
    nodes = ("v1", "v2", "v3", "v4")
    positions.update(zip(nodes, range(1, 5)))
    neighbors = defaultdict(list, {
        "v1": ["u1", "u2", "u3", "u4", "u5"],
        "v2": ["u6"],
        "v3": ["u7", "u8", "u9"],
        "v4": ["u7", "u9"],
    })
    _improve_level(nodes, positions, neighbors, {"v2"})
    assert [positions[node] for node in nodes] == [3, 6, 8, 9]


def test_condensation_contracts_a_cycle_and_keeps_the_outgoing_relation():
    result = condense_cycles((0, 1, 2, 3), ((0, 1), (1, 2), (2, 0), (2, 3)))
    component, sink = result.nodes
    assert component.members == {0, 1, 2}
    assert result.edges == ((component, sink),)
    assert not result.reversed_edges
