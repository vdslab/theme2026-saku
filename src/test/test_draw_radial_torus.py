import matplotlib

matplotlib.use("Agg")

from drawing.draw_radial_torus import draw_radial_torus


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
