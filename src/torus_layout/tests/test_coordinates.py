import copy
import random
import pytest
from torus_layout import Graph
from torus_layout.models import CrossingResult, LayerAssignmentResult, SubdividedGraph
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import reduce_crossings
from torus_layout.coordinates import assign_coordinates
from old_torus_layout.coordinate_assignment.brandes_koepf import (
    assign_torus_brandes_koepf_coordinates as legacy,
)


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("gap", [0.5, 1.0, 2.0])
@pytest.mark.parametrize("iterations", [0, 4])
def test_coordinates_match_legacy(seed, gap, iterations):
    rng = random.Random(seed)
    nodes = tuple(range(12))
    ranks = {node: node // 4 for node in nodes}
    edges = tuple(
        (u, v)
        for u in nodes
        for v in nodes
        if ranks[u] != ranks[v] and rng.random() < 0.18
    )
    flags = {edge: ranks[edge[0]] > ranks[edge[1]] for edge in edges}
    divided = insert_dummy_nodes(
        Graph(nodes, edges), LayerAssignmentResult(ranks, flags, 0)
    )
    crossing = reduce_crossings(divided, 1)
    before = copy.deepcopy((divided, crossing))
    expected = legacy(
        crossing.order,
        divided.layers,
        list(divided.graph.edges),
        divided.torus_flags,
        crossing.winding_numbers,
        gap,
        iterations,
        nodes,
    )
    actual = assign_coordinates(
        divided, crossing, min_gap=gap, smooth_iterations=iterations, method="brandes_koepf",
    )
    assert actual.positions.keys() == expected.keys()
    for node, position in expected.items():
        assert actual.positions[node] == pytest.approx(position, abs=1e-10)
    assert actual.period == max(len(ns) for ns in crossing.order.values()) * gap
    assert (divided, crossing) == before


def test_existing_coordinate_regressions_with_new_implementation(monkeypatch):
    import importlib.util
    from pathlib import Path
    from torus_layout.coordinates.api import compute_positions

    path = Path(__file__).resolve().parents[2] / "old_torus_layout/tests/test_coordinate_assignment.py"
    spec = importlib.util.spec_from_file_location("coordinate_regressions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module, "assign_torus_brandes_koepf_coordinates", compute_positions
    )
    for name in dir(module):
        if name.startswith("test_"):
            getattr(module, name)()


@pytest.mark.parametrize(
    "middle_layers, winding, expected",
    [
        (([2], [3, 5]), 0, (0, 0)),
        (([2], [3, 5]), 1, (1, 0)),
        (([2, 7], [5, 3]), 0, (0, 1)),
    ],
)
def test_block_coordinates_join_dummy_paths_when_straight_and_feasible(
    middle_layers, winding, expected,
):
    order = {0: [4, 0], 1: middle_layers[0], 2: middle_layers[1], 3: [6, 1]}
    nodes = tuple(node for layer in order.values() for node in layer)
    edges = ((0, 2), (2, 3), (3, 1))
    graph = SubdividedGraph(
        Graph(nodes, edges), order, {}, {}, tuple(node for node in nodes if node not in (2, 3)),
    )
    crossing = CrossingResult(order, {(2, 3): winding})
    result = assign_coordinates(graph, crossing, method="brandes_koepf_blocks", min_gap=0.5)

    assert result.period == 1.0
    assert (result.positions[2][1], result.positions[3][1]) == tuple(
        rank * 0.5 for rank in expected
    )
    for layer, members in order.items():
        assert all(result.positions[node][0] == layer for node in members)
        ys = [result.positions[node][1] for node in members]
        assert all(b - a >= 0.5 for a, b in zip(ys, ys[1:]))
        assert ys[0] + result.period - ys[-1] >= 0.5


def test_default_unsplit_blocks_expand_period_only_as_needed():
    order = {0: [0], 1: [2, 4], 2: [5, 3], 3: [1]}
    nodes = (0, 1, 4, 5, 2, 3)
    edges = ((0, 2), (2, 3), (3, 1))
    graph = SubdividedGraph(Graph(nodes, edges), order, {}, {}, (0, 1, 4, 5))
    crossing = CrossingResult(order, {})

    result = assign_coordinates(graph, crossing, min_gap=0.5)

    assert result.period == 1.5
    assert result.positions[2][1] == result.positions[3][1] == 0.5
    for members in order.values():
        ys = [result.positions[node][1] for node in members]
        assert all(b - a >= 0.5 for a, b in zip(ys, ys[1:]))
        assert ys[0] + result.period - ys[-1] >= 0.5
