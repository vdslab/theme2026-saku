import copy
from dataclasses import replace
from io import BytesIO

import matplotlib.pyplot as plt
import pytest
from PIL import Image, ImageChops

from torus_layout import Graph
from torus_layout.models import SubdividedGraph, CrossingResult, CoordinateResult
from torus_layout.drawing import DrawingOptions, create_figure, draw_layout
from torus_layout.drawing.geometry import periodic_edge_segments
from old_torus_layout.drawing.draw_radial_torus import draw_radial_torus, _periodic_edge_segments


def drawing_case():
    nodes = tuple(range(6))
    originals = (0, 2, 3, 4, 5)
    edges = ((0, 2), (4, 0), (1, 3), (2, 5), (5, 1), (4, 1))
    layers = {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    flags = {(4, 0): True, (5, 1): True, (4, 1): True}
    winding = {(1, 3): 1, (2, 5): -1, (5, 1): 1, (4, 1): -1}
    graph = SubdividedGraph(
        Graph(nodes, edges), layers, flags, {e: 1 for e in edges}, originals
    )
    crossing = CrossingResult(copy.deepcopy(layers), winding)
    positions = {n: (float(n // 2), float(n % 2)) for n in nodes}
    return graph, crossing, CoordinateResult(positions, 2.0)


@pytest.mark.parametrize("tile", [False, True])
@pytest.mark.parametrize("show_dummy", [False, True])
@pytest.mark.parametrize("supplied_positions", [False, True])
def test_rendered_pixels_match_legacy(tmp_path, tile, show_dummy, supplied_positions):
    graph, crossing, coordinates = drawing_case()
    before = copy.deepcopy((graph, crossing, coordinates))
    old_path = tmp_path / "old.png"
    new_path = tmp_path / "new.png"
    draw_radial_torus(
        list(graph.original_nodes),
        list(graph.graph.edges),
        graph.layers,
        order=crossing.order,
        psi=crossing.winding_numbers,
        t_val=graph.torus_flags,
        pos=coordinates.positions if supplied_positions else None,
        save_path=old_path,
        show=False,
        draw_dummy_nodes=show_dummy,
        dpi=60,
        tile_surroundings=tile,
        surrounding_opacity=0.5,
        tile_gap=2,
    )
    options = DrawingOptions(
        draw_dummy_nodes=show_dummy,
        dpi=60,
        tile_surroundings=tile,
        surrounding_opacity=0.5,
        tile_gap=2,
    )
    draw_layout(
        graph,
        crossing,
        coordinates if supplied_positions else None,
        options=options,
        save_path=new_path,
        show=False,
    )
    with Image.open(old_path) as old, Image.open(new_path) as new:
        assert old.size == new.size
        assert old.convert("RGBA").tobytes() == new.convert("RGBA").tobytes()
    assert (graph, crossing, coordinates) == before


def test_create_figure_and_vector_output(tmp_path):
    graph, crossing, coordinates = drawing_case()
    before = plt.get_fignums()
    fig = create_figure(graph, crossing, coordinates)
    assert fig.axes
    fig.savefig(tmp_path / "layout.svg")
    assert "<svg" in (tmp_path / "layout.svg").read_text()
    plt.close(fig)
    assert plt.get_fignums() == before
    draw_layout(graph, crossing, coordinates, show=False)
    assert plt.get_fignums() == before


@pytest.mark.parametrize(
    "horizontal,vertical", [(0, 0), (1, 0), (0, 1), (1, -1), (2, 3), (-1, -2)]
)
def test_periodic_geometry_matches_legacy(horizontal, vertical):
    kwargs = dict(
        x_min=-0.5,
        x_max=2.5,
        y_min=-0.5,
        y_max=1.5,
        horizontal_winding=horizontal,
        vertical_winding=vertical,
    )
    assert periodic_edge_segments((0, 0), (2, 1), **kwargs) == _periodic_edge_segments(
        (0, 0), (2, 1), **kwargs
    )


def test_tiled_vector_path_is_rejected_as_before(tmp_path):
    graph, crossing, coordinates = drawing_case()
    with pytest.raises(ValueError, match="raster"):
        draw_layout(
            graph,
            crossing,
            coordinates,
            options=DrawingOptions(tile_surroundings=True),
            save_path=tmp_path / "invalid.svg",
            show=False,
        )


@pytest.mark.parametrize("winding", [2, -2, 3, -3])
@pytest.mark.parametrize("horizontal_wrap", [False, True])
def test_drawn_edge_preserves_full_winding(monkeypatch, winding, horizontal_wrap):
    """Check actual renderer segments, not just the unused geometry helper."""
    from torus_layout.drawing import artists

    layers = {0: [0, 2, 3, 4], 1: [1, 5, 6, 7]}
    source_x, target_x = (1.0, 0.0) if horizontal_wrap else (0.0, 1.0)
    if horizontal_wrap:
        layers = {0: [1, 2, 3, 4], 1: [0, 5, 6, 7]}
    source_y, target_y = (3.0, 0.0) if winding > 0 else (0.0, 3.0)
    positions = {node: (float(layer), float(index))
                 for layer, nodes in layers.items() for index, node in enumerate(nodes)}
    positions.update({0: (source_x, source_y), 1: (target_x, target_y)})
    edge = (0, 1)
    graph = SubdividedGraph(
        Graph(tuple(positions), (edge,)), layers, {edge: horizontal_wrap},
        {edge: 1}, (0, 1),
    )
    calls = []

    def capture(ax, start, end, style, edge_width, **kwargs):
        calls.append((start, end, kwargs))

    monkeypatch.setattr(artists, "add_edge_patch", capture)
    figure = create_figure(
        graph, CrossingResult(layers, {edge: winding}),
        CoordinateResult(positions, 4.0),
    )
    plt.close(figure)
    assert calls[0][0] == positions[0]
    assert calls[-1][1] == pytest.approx(positions[1])
    assert sum(end[0] - start[0] for start, end, _ in calls) == pytest.approx(
        target_x - source_x + 2 * int(horizontal_wrap)
    )
    assert sum(end[1] - start[1] for start, end, _ in calls) == pytest.approx(
        target_y - source_y + 4 * winding
    )
    assert sum(options["arrow"] for _, _, options in calls) == 1
    assert calls[-1][2]["arrow"] is True
    for _, _, options in calls[1:]:
        assert options.get("shrink_a", 0) == 0
    for _, _, options in calls[:-1]:
        assert options.get("shrink_b", 0) == 0


@pytest.mark.parametrize("winding", [1.5, float("nan"), float("inf")])
def test_drawing_rejects_winding_without_a_periodic_endpoint(winding):
    graph, crossing, coordinates = drawing_case()
    crossing.winding_numbers[1, 3] = winding
    with pytest.raises(ValueError, match="integer winding"):
        create_figure(graph, crossing, coordinates)
