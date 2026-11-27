import math

import matplotlib.pyplot as plt

from radial_layout import (
    DummyNode, assign_coordinates, count_crossings, insert_dummy_nodes, reduce_crossings,
)
from radial_layout.crossing_reduction import RadialEmbedding, rotate_level
from radial_layout.drawing import _sample_chain, create_radial_figure


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
    assert coords.winding["center", "a"] == 0
    assert all(math.isclose(px * y - py * x, 0, abs_tol=1e-12) for px, py in points)


def test_postprocessing_reduces_the_signed_span_of_the_drawn_spiral():
    layers = {0: ("a", "b", "c"), 1: ("x", "y", "z")}
    embedding = reduce_crossings(layers, (("a", "y"),))
    target_turn = embedding.order[1].index("y") / len(layers[1])
    assert target_turn + embedding.winding["a", "y"] == 0
    assert embedding.crossings == 0


def test_center_spokes_have_zero_offset_after_sifting():
    layers = {0: ("root",), 1: ("a", "b", "c"), 2: ("x", "y", "z")}
    spokes = (("root", "a"), ("root", "b"), ("root", "c"))
    edges = spokes + (("a", "z"), ("b", "y"), ("c", "x"))
    embedding = reduce_crossings(layers, edges)
    assert all(embedding.winding[edge] == 0 for edge in spokes)
    assert embedding.crossings == count_crossings(embedding.order, edges, embedding.winding)


def test_reordered_dummy_chains_keep_sifting_result_drawable():
    inner = tuple(DummyNode(i, 1) for i in range(3))
    outer = tuple(DummyNode(i, 2) for i in range(3))
    edges = tuple(zip(inner, outer))
    layers = {1: inner, 2: outer[::-1]}
    assert count_crossings(layers, edges) == 3
    embedding = reduce_crossings(layers, edges)
    coordinates = assign_coordinates(embedding)
    assert embedding.crossings == 0
    assert all(coordinates.polar[u][1] == coordinates.polar[v][1] for u, v in edges)


def test_long_spiral_chords_stay_in_the_band_and_move_outwards():
    polar = {"a": (20.0, 1.0), "b": (21.0, 2.0)}
    points = _sample_chain(("a", "b"), polar, {("a", "b"): 3})
    for a, b in zip(points, points[1:]):
        # The derivative of the squared radius of the chord is increasing.
        assert sum(x * (y - x) for x, y in zip(a, b)) > 0


def test_crowded_ring_markers_fit_a_fixed_canvas():
    nodes = tuple(range(30))
    coords = assign_coordinates({0: nodes})
    fig = create_radial_figure(
        nodes, (), coords.cartesian, coords.polar, coords.radii, {}, {}, frozenset(),
        figsize=(4, 4),
    )
    try:
        fig.canvas.draw()
        axis, = fig.axes
        markers, = axis.collections
        centers = axis.transData.transform([coords.cartesian[n] for n in nodes])
        neighbor_distance = min(math.dist(p, q) for p, q in zip(centers, centers[1:]))
        diameter = (math.sqrt(markers.get_sizes()[0]) + markers.get_linewidths()[0]) * fig.dpi / 72
        assert diameter < neighbor_distance
    finally:
        plt.close(fig)
