"""Verify the comparison budget and parity with the production schedules."""

import importlib.util
from pathlib import Path

import crossing_reduction.radial as radial

spec = importlib.util.spec_from_file_location(
    "sweep_experiment", Path(__file__).resolve().parents[2] / "experiments/evaluate_torus_sweep_direction.py"
)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def test_direction_and_equal_budgets():
    layers = [1, 2, 3]
    schedules = {m: experiment.schedule(layers, m, rounds=5) for m in experiment.METHODS}
    assert {len(pairs) for pairs in schedules.values()} == {25}
    assert schedules["cyclic"][:7] == [(1, 2), (2, 3), (3, 1), (1, 2), (2, 3), (3, 1), (1, 2)]
    assert schedules["alternating"][:7] == [(1, 2), (2, 3), (3, 1), (1, 3), (3, 2), (2, 1), (1, 2)]
    assert experiment.schedule([1], "cyclic") == []


def test_current_schedule_results_match_production():
    initial = {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    layers = sorted(initial)
    edges = [(0, 3), (1, 2), (2, 5), (3, 4), (4, 1), (5, 0)]
    winding = {e: 0 for e in edges}
    result, trace = experiment.evaluate(initial, winding, layers, edges, set(), experiment.schedule(layers, "current_cyclic", rounds=2))
    order, psi = radial._copy_order(initial), dict(winding)
    radial._run_sifting(order, psi, layers, edges, 2, dummy_nodes=set())
    radial._postprocess_sifting_rotations(order, psi, layers, edges)
    assert result["final_crossings"] == radial._count_all_crossings(order, psi, layers, edges)
    order, psi = radial._copy_order(initial), dict(winding)
    radial._run_sifting_with_global_guard(order, psi, layers, edges, 2, dummy_nodes=set())
    before_rotation = radial._count_all_crossings(order, psi, layers, edges)
    radial._postprocess_sifting_rotations(order, psi, layers, edges)
    assert result["guarded_crossings"] == min(before_rotation, radial._count_all_crossings(order, psi, layers, edges))
    assert result["guarded_crossings"] <= trace[0]["crossings"]
    assert initial == {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    assert winding == {e: 0 for e in edges}


def test_full_circulation_uses_every_layer_for_general_layer_counts():
    layers = [10, 20, 30, 40, 50, 60, 70, 80]
    pairs = experiment.schedule(layers, "cyclic", rounds=5)
    assert len(pairs) == 75
    assert pairs[:8] == [(10, 20), (20, 30), (30, 40), (40, 50),
                         (50, 60), (60, 70), (70, 80), (80, 10)]
    assert pairs[8:16] == pairs[:8]


def test_ws100_design_and_complex_network_generator(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "experiments"))
    import evaluate_torus_sweep_ws100 as ws
    parameters = ws.parameters()
    assert len(parameters) == 100
    assert sorted({p["nodes"] for p in parameters}) == list(range(10, 101, 10))
    assert all(sum(p["nodes"] == n for p in parameters) == 10 for n in range(10, 101, 10))
    assert {(p["neighbors"], p["rewiring_probability"]) for p in parameters} == {(4, 0.8)}
    vertices, edges = experiment.generate_watts_strogatz_graph(100, k=4, p=0.8, seed=0)
    assert len(vertices) == 100
    assert len(set(edges)) == 200
    import networkx as nx
    assert nx.is_connected(nx.Graph(edges))
