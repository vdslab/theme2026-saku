import copy
import random
import pytest
from torus_layout.models import Graph, SubdividedGraph, CrossingResult, LayerAssignmentResult
from torus_layout.coordinates import assign_coordinates
from torus_layout.coordinates import optimization
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import reduce_crossings


def energy(graph, crossing, result, power=2):
    return sum(graph.weights.get((u, v), 1) * abs(
        result.positions[v][1] - result.positions[u][1]
        + crossing.winding_numbers.get((u, v), 0) * result.period
    ) ** power for u, v in graph.graph.edges)


@pytest.mark.parametrize('method,power', [('torus_qp', 2), ('torus_lp', 1)])
@pytest.mark.parametrize('seed', range(8))
def test_periodic_optimizer_preserves_embedding_and_improves(method, power, seed, local_solver, monkeypatch):
    monkeypatch.setattr(optimization, 'create_gurobi_env', local_solver)
    rng = random.Random(seed)
    ranks = {i: i // 3 for i in range(12)}
    edges = tuple((u, v) for u in ranks for v in ranks
                  if ranks[u] != ranks[v] and rng.random() < .17)
    graph = insert_dummy_nodes(Graph(tuple(ranks), edges), LayerAssignmentResult(
        ranks, {e: ranks[e[0]] > ranks[e[1]] for e in edges}, 0))
    crossing = reduce_crossings(graph, 1)
    before = copy.deepcopy((graph, crossing))
    bk = assign_coordinates(graph, crossing)
    result = assign_coordinates(graph, crossing, method=method)
    assert energy(graph, crossing, result, power) <= energy(graph, crossing, bk, power) + 1e-6
    for nodes in crossing.order.values():
        ys = [result.positions[n][1] for n in nodes]
        assert all(b - a >= 1 - 1e-7 for a, b in zip(ys, ys[1:]))
        if ys:
            assert ys[0] + result.period - ys[-1] >= 1 - 1e-7
        assert all(-.5 < y < result.period - .5 for y in ys)
    assert (graph, crossing) == before


def test_signed_winding_and_horizontal_wrap(local_solver, monkeypatch):
    monkeypatch.setattr(optimization, 'create_gurobi_env', local_solver)
    # Closing edge in x must be included. psi=+1 gives y[a]-y[b]+H.
    graph = SubdividedGraph(Graph(('a', 'b'), (('b', 'a'),)),
                            {0: ['a'], 1: ['b']}, {('b', 'a'): True}, {}, ('a', 'b'))
    crossing = CrossingResult(graph.layers, {('b', 'a'): 1})
    result = assign_coordinates(graph, crossing, method='torus_qp')
    assert energy(graph, crossing, result) < 1e-10
    assert result.positions['b'][1] > result.positions['a'][1] + .999


@pytest.mark.parametrize("period", [2.0, 2.5, 3.2])
def test_expanded_lp_domain_is_accepted_by_drawing(period, local_solver, monkeypatch):
    from torus_layout.coordinates import api
    from torus_layout.drawing.preparation import prepare_drawing

    monkeypatch.setattr(optimization, "create_gurobi_env", local_solver)
    monkeypatch.setattr(api, "drawing_period", lambda *args: period)
    graph = SubdividedGraph(Graph((0, 1, 2), ((0, 2), (1, 2))),
                            {0: [0, 1], 1: [2]}, {}, {}, (0, 1, 2))
    crossing = CrossingResult(graph.layers, {(0, 2): -1})
    result = assign_coordinates(graph, crossing, method="torus_lp")
    prepare_drawing(list(graph.original_nodes), list(graph.graph.edges), graph.layers,
                    crossing.order, crossing.winding_numbers, pos=result.positions,
                    vertical_period=result.period)


def test_dummy_bend_reduction(local_solver, monkeypatch):
    monkeypatch.setattr(optimization, 'create_gurobi_env', local_solver)
    graph = SubdividedGraph(Graph(('a', 'd', 'b'), (('a', 'd'), ('d', 'b'))),
                            {0: ['a'], 1: ['d'], 2: ['b']}, {}, {}, ('a', 'b'))
    crossing = CrossingResult(graph.layers, {('d', 'b'): 1})
    result = assign_coordinates(graph, crossing, method='torus_qp', bend_weight=2)
    ya, yd, yb = [result.positions[n][1] for n in ('a', 'd', 'b')]
    assert yd - ya == pytest.approx(yb - yd + result.period, abs=1e-5)


@pytest.mark.parametrize('method', ['torus_lp', 'torus_qp'])
def test_empty_and_invalid_inputs(method):
    graph = SubdividedGraph(Graph((), ()), {}, {}, {}, ())
    assert assign_coordinates(graph, CrossingResult({}, {}), method=method).positions == {}
    with pytest.raises(ValueError):
        assign_coordinates(graph, CrossingResult({}, {}), method=method, bend_weight=-1)


def test_pipeline_selects_optimizer(local_solver, monkeypatch):
    from torus_layout.layering.balance import diff_square
    from torus_layout.layering import minimize_wraps
    from torus_layout.pipeline import run_pipeline
    for module in (optimization, diff_square, minimize_wraps):
        monkeypatch.setattr(module, 'create_gurobi_env', local_solver)
    result = run_pipeline(Graph((0, 1, 2), ((0, 1), (1, 2), (2, 0))))
    assert result is not None
    assert len(result.coordinates.positions) == 3


@pytest.mark.parametrize('method,optimum', [('torus_qp', 4/7), ('torus_lp', 1)])
def test_weighted_cycle_matches_analytic_optimum(method, optimum, local_solver, monkeypatch):
    monkeypatch.setattr(optimization, 'create_gurobi_env', local_solver)
    edges = (('a', 'b'), ('b', 'c'), ('c', 'a'))
    graph = SubdividedGraph(Graph(('a', 'b', 'c'), edges),
                            {0: ['a'], 1: ['b'], 2: ['c']},
                            {edges[-1]: True}, dict(zip(edges, (1, 2, 4))), ('a', 'b', 'c'))
    crossing = CrossingResult(graph.layers, {edges[-1]: 1})
    result = assign_coordinates(graph, crossing, method=method)
    # Sum of lifted displacements is H=1. Weighted Cauchy-Schwarz gives
    # QP optimum 1 / (1 + 1/2 + 1/4); L1 puts displacement on cheapest edge.
    assert energy(graph, crossing, result, 2 if method == 'torus_qp' else 1) == pytest.approx(optimum, abs=1e-6)
