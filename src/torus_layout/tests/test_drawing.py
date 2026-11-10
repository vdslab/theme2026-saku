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
