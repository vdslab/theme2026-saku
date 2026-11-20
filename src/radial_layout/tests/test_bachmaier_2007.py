import math

from radial_layout import assign_coordinates, count_crossings, insert_dummy_nodes, reduce_crossings
from radial_layout.crossing_reduction import RadialEmbedding, rotate_level
from radial_layout.drawing import _sample_chain


def test_clockwise_rotation_preserves_both_boundaries():
    order = {0: ["a", "b"], 1: ["c", "d"], 2: ["e", "f"]}
    incoming = (("a", "c"), ("b", "d"))
    outgoing = (("c", "f"), ("d", "e"))
    winding = dict.fromkeys(incoming + outgoing, 0)
    before = count_crossings(order, incoming + outgoing, winding)
    rotate_level(order, winding, 1, 1, incoming, outgoing)
    assert order[1] == ["d", "c"]
    assert winding["a", "c"] == -1
    assert winding["c", "f"] == 1
    assert count_crossings(order, incoming + outgoing, winding) == before


def test_unwinding_and_compaction_align_long_edge_inner_segments():
    hierarchy = insert_dummy_nodes(
        (0, 1, 2, 3, 4, 5), ((0, 4), (0, 5), (1, 2), (2, 3), (3, 4)),
        {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 3},
    )
    winding = dict.fromkeys(hierarchy.edges, 0)
    inner = [edge for edge in hierarchy.edges if set(edge) <= hierarchy.dummy_nodes]
    for edge in inner:
        winding[edge] = 3
    embedding = RadialEmbedding(hierarchy.layers, winding,
                                count_crossings(hierarchy.layers, hierarchy.edges, winding))
    coords = assign_coordinates(embedding)
    assert coords.radii[0] == coords.radii[1] / 3
    for u, v in inner:
        assert coords.winding[u, v] == 0
        assert math.isclose(coords.polar[u][1], coords.polar[v][1])
    assert all(winding[edge] == 3 for edge in inner)


def test_sifting_optimizes_explicit_edge_offsets():
    layers = {0: ("a", "b", "c"), 1: ("x", "y", "z")}
    edges = tuple(map(tuple, ("ax", "az", "bx", "by", "cy", "cz")))
    result = reduce_crossings(layers, edges)
    assert result.crossings == 0
    assert result.crossings == count_crossings(result.order, edges, result.winding)


def test_center_edges_are_straight_even_when_offset_was_nonzero():
    embedding = RadialEmbedding({0: ("center",), 1: ("a", "b")}, {("center", "a"): 1}, 0)
    coords = assign_coordinates(embedding)
    points = _sample_chain(("center", "a"), coords.polar, coords.winding)
    x, y = coords.cartesian["a"]
    assert coords.cartesian["center"] == (0, 0)
    assert all(math.isclose(px * y - py * x, 0, abs_tol=1e-12) for px, py in points)


def test_postprocessing_uses_algorithm_two_rotation_direction():
    layers = {0: ("a", "b", "c"), 1: ("x", "y", "z")}
    embedding = reduce_crossings(layers, (("a", "y"),))
    assert embedding.order[1] == ("z", "x", "y")
    assert embedding.crossings == 0
