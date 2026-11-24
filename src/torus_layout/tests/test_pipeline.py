import copy
import pytest
from torus_layout import Graph
from generator import generate_graph
from torus_layout.crossing.seam import seam_score
from torus_layout.models import LayerAssignmentResult, LayerSearchResult, PipelineConfig
from torus_layout.pipeline import run_pipeline
from torus_layout.reporting import report_pipeline
from torus_layout.layering.balance import diff, diff_square, qp
from torus_layout.layering import minimize_wraps
from old_torus_layout.layer_assignment import torus_balance as old_balance, torus_two_stage as old_min
import old_torus_layout.main as legacy

CASES = [
    ((0, 1, 2), ((0, 1), (1, 2))),
    ((0, 1, 2), ((0, 1), (1, 2), (2, 0))),
    ((0, 1, 2, 3), ((0, 1), (0, 2), (1, 3), (2, 3))),
    ((0, 1, 2, 3, 4), ((0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2))),
]


@pytest.mark.parametrize("method", ["diff", "diff_square", "qp", "barycenter"])
@pytest.mark.parametrize("nodes,edges", CASES)
def test_pipeline_matches_existing_path(
    nodes, edges, method, local_solver, monkeypatch, capsys
):
    for module in (diff, diff_square, qp, minimize_wraps, old_balance, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    graph = Graph(nodes, edges)
    before = copy.deepcopy(graph)
    assigned = legacy.layer_assignment(list(nodes), list(edges), method)
    layers, flags, _, _ = assigned
    expected = legacy.reduce_crossings_radial(
        list(nodes), list(edges), layers, flags, 2
    )
    order, divided_layers, divided_edges, divided_flags, winding, _ = expected
    positions = legacy.assign_torus_brandes_koepf_coordinates(
        order, divided_layers, divided_edges, divided_flags, winding, smooth_iterations=0, original_nodes=list(nodes)
    )
    actual = run_pipeline(graph, PipelineConfig(
        method, 2, coordinate_method="brandes_koepf", optimize_seams=False, unwind_levels=False,
        sifting_method="parting",
    ))
    assert actual is not None
    assert actual.assignment.layers == layers
    assert actual.assignment.torus_flags == flags
    assert actual.subdivided.layers == divided_layers
    assert list(actual.subdivided.graph.edges) == divided_edges
    assert actual.subdivided.torus_flags == divided_flags
    assert actual.crossing.order == order
    assert actual.crossing.winding_numbers == winding
    for node, position in positions.items():
        assert actual.coordinates.positions[node] == pytest.approx(position, abs=1e-10)
    assert actual.crossing_time >= 0 and actual.coordinate_time >= 0
    assert graph == before
    capsys.readouterr()
    report_pipeline(actual)
    assert "交差数" in capsys.readouterr().out


def test_empty_graph_keeps_none_result(local_solver, monkeypatch):
    for module in (diff, diff_square, qp, minimize_wraps, old_balance, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    assert legacy.layer_assignment([], [], "diff_square") is None
    assert run_pipeline(Graph((), ())) is None


def test_joint_seam_uses_zero_internal_legacy_cut_if_unsplit_order_cycles(monkeypatch):
    from torus_layout import pipeline

    nodes, edges, _ = generate_graph("random", 12, seed=3, edge_prob=0.16)
    graph = Graph(tuple(nodes), tuple(edges))
    ranks = dict(zip(nodes, (0, 1, 4, 3, 3, 6, 1, 5, 3, 2, 1, 2)))
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    assigned = LayerAssignmentResult(ranks, flags, 0)
    search = LayerSearchResult(7, sum(flags.values()), 0)
    monkeypatch.setattr(pipeline, "assign_layers", lambda *_: (search, assigned))

    with pytest.warns(UserWarning, match="従来方式を適用"):
        joint = run_pipeline(graph, PipelineConfig(rounds=2))
    legacy = run_pipeline(graph, PipelineConfig(rounds=2, seam_method="legacy"))
    assert joint is not None and legacy is not None
    assert joint.seam_method_used == "legacy"
    assert joint.crossing == legacy.crossing
    assert joint.coordinates == legacy.coordinates
    assert seam_score(joint.subdivided, joint.crossing, True) == (0, 5)


def test_original_main_and_new_pipeline_save_identical_image(
    tmp_path, local_solver, monkeypatch
):
    import random
    from PIL import Image
    from torus_layout.drawing import draw_layout
    from old_torus_layout.lib.generate_torus_graph import generate_cyclic_graph

    for module in (diff, diff_square, qp, minimize_wraps, old_balance, old_min):
        monkeypatch.setattr(module, "create_gurobi_env", local_solver)
    old_path = tmp_path / "original-main.png"
    new_path = tmp_path / "new-pipeline.png"
    state = random.getstate()
    try:
        legacy.main(
            node=6,
            cycle=2,
            prob=0,
            seed=42,
            rounds=2,
            func_type="diff_square",
            save_path=old_path,
            show=False,
            draw_dummy_nodes=False,
            tile_surroundings=False,
        )
        nodes, edges, _ = generate_cyclic_graph(6, num_cycles=2, edge_prob=0, seed=42)
    finally:
        random.setstate(state)
    result = run_pipeline(Graph(tuple(nodes), tuple(edges)), PipelineConfig(
        rounds=2, coordinate_method="brandes_koepf", optimize_seams=False, unwind_levels=False,
        sifting_method="parting",
    ))
    assert result is not None
    draw_layout(
        result.subdivided,
        result.crossing,
        result.coordinates,
        save_path=new_path,
        show=False,
    )
    with Image.open(old_path) as old, Image.open(new_path) as new:
        assert old.size == new.size
        assert old.convert("RGBA").tobytes() == new.convert("RGBA").tobytes()
