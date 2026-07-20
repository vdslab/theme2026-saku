import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from drawing.draw_radial_torus import _periodic_edge_segments, draw_radial_torus
from drawing.tile_image import create_torus_context_image
from PIL import Image


def _sample_graph():
    layers = {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    edges = [(0, 2), (1, 3), (2, 5), (4, 0)]
    t_val = {edge: edge == (4, 0) for edge in edges}
    psi = {edge: 0 for edge in edges}
    psi[(1, 3)] = 1
    psi[(2, 5)] = -1
    pos = {
        0: (0.0, 0.0),
        1: (0.0, 1.0),
        2: (1.0, 0.0),
        3: (1.0, 1.0),
        4: (2.0, 0.0),
        5: (2.0, 1.0),
    }
    return layers, edges, t_val, psi, pos


def test_draw_radial_torus_saves_vector_figure(tmp_path):
    layers, edges, t_val, psi, pos = _sample_graph()
    output = tmp_path / "flat_torus.svg"

    draw_radial_torus(
        V=list(range(6)),
        A=edges,
        L=layers,
        order=layers,
        psi=psi,
        t_val=t_val,
        pos=pos,
        save_path=output,
        show=False,
    )

    content = output.read_text(encoding="utf-8").lower()
    assert output.stat().st_size > 1000
    assert "#d55e00" in content
    assert "#0072b2" in content
    assert "#cc79a7" in content
    assert "ordinary" in content


def test_draw_radial_torus_rejects_missing_positions():
    layers, edges, t_val, psi, pos = _sample_graph()
    pos.pop(5)

    try:
        draw_radial_torus(
            V=list(range(6)),
            A=edges,
            L=layers,
            order=layers,
            psi=psi,
            t_val=t_val,
            pos=pos,
            show=False,
        )
    except ValueError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("missing positions must be rejected")


def test_draw_radial_torus_supports_combined_horizontal_and_vertical_wrap(tmp_path):
    layers, _, _, _, pos = _sample_graph()
    edges = [(4, 1), (5, 0)]
    t_val = {edge: True for edge in edges}
    psi = {(4, 1): 1, (5, 0): -1}
    output = tmp_path / "combined_wrap.svg"

    draw_radial_torus(
        V=list(range(6)),
        A=edges,
        L=layers,
        order=layers,
        psi=psi,
        t_val=t_val,
        pos=pos,
        save_path=output,
        show=False,
    )

    content = output.read_text(encoding="utf-8").lower()
    assert "#009e73" in content
    assert "#882255" in content
    assert "horizontal +" in content


def test_combined_wrap_is_split_at_both_boundaries():
    segments = _periodic_edge_segments(
        (2.0, 0.2),
        (0.0, 1.0),
        x_min=-0.5,
        x_max=2.5,
        y_min=-0.5,
        y_max=1.5,
        horizontal_winding=1,
        vertical_winding=1,
    )

    # この配置では先に上境界、次に右境界を横切るため3本になる。
    assert len(segments) == 3
    assert segments[0][0] == (2.0, 0.2)
    assert segments[-1][1] == (0.0, 1.0)
    for segment in segments:
        for x, y in segment:
            assert -0.5 <= x <= 2.5
            assert -0.5 <= y <= 1.5


def test_create_torus_context_image_keeps_center_and_fades_neighbors(tmp_path):
    source = Image.new("RGBA", (2, 3), (10, 20, 30, 200))
    output = tmp_path / "torus_context.png"

    result = create_torus_context_image(
        source, opacity=0.25, gap=1, output_path=output
    )

    assert result.size == (8, 11)
    assert result.getpixel((3, 4)) == (10, 20, 30, 200)
    assert result.getpixel((0, 0)) == (10, 20, 30, 50)
    assert result.getpixel((2, 0)) == (255, 255, 255, 0)
    assert Image.open(output).size == result.size


def test_create_torus_context_image_can_draw_light_tile_borders():
    source = Image.new("RGBA", (3, 3), (255, 255, 255, 255))

    result = create_torus_context_image(
        source,
        opacity=1.0,
        border_width=1,
        border_color=(0, 0, 0, 72),
    )

    # 境界線は半透明黒を白へ重ねた薄い灰色になる。
    assert result.getpixel((3, 4)) == (183, 183, 183, 255)
    assert result.getpixel((4, 4)) == (255, 255, 255, 255)


def test_draw_radial_torus_can_save_surrounding_tiles(tmp_path):
    layers, edges, t_val, psi, pos = _sample_graph()
    output = tmp_path / "tiled_torus.png"

    draw_radial_torus(
        V=list(range(6)),
        A=edges,
        L=layers,
        order=layers,
        psi=psi,
        t_val=t_val,
        pos=pos,
        save_path=output,
        show=False,
        tile_surroundings=True,
        surrounding_opacity=0.15,
        dpi=80,
    )

    with Image.open(output) as tiled:
        width, height = tiled.size
        assert width % 3 == 0
        assert height % 3 == 0
        # 枠・凡例・目盛りを含まず、データ領域（幅3、高さ2）の比率になる。
        assert abs((width / 3) / (height / 3) - 1.5) < 0.02


def test_draw_radial_torus_can_render_tiles_without_save_path():
    layers, edges, t_val, psi, pos = _sample_graph()

    draw_radial_torus(
        V=list(range(6)),
        A=edges,
        L=layers,
        order=layers,
        psi=psi,
        t_val=t_val,
        pos=pos,
        save_path=None,
        show=False,
        tile_surroundings=True,
        dpi=40,
    )


def test_tiled_display_closes_small_source_figure_before_show(monkeypatch):
    layers, edges, t_val, psi, pos = _sample_graph()
    open_figure_counts = []
    monkeypatch.setattr(
        plt, "show", lambda: open_figure_counts.append(len(plt.get_fignums()))
    )

    draw_radial_torus(
        V=list(range(6)),
        A=edges,
        L=layers,
        order=layers,
        psi=psi,
        t_val=t_val,
        pos=pos,
        show=True,
        tile_surroundings=True,
        dpi=40,
    )

    assert open_figure_counts == [1]
    assert plt.get_fignums() == []
