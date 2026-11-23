"""元実装と同じ上限・判定でレイヤー数を二分探索する。"""

from time import perf_counter

from ..models import Graph, Node, Edge, Weights, LayerSearchResult
from .minimize_wraps import solve_fixed_layers


def find_minimum_torus_configuration(
    V: list[Node],
    A: list[Edge],
    w: Weights | None = None,
    lam: dict[Edge, int] | None = None,
) -> tuple[int | None, int | None, float]:
    result = find_minimum_configuration(Graph(tuple(V), tuple(A)), w, lam)
    return result.layer_count, result.torus_count, result.runtime


def find_minimum_configuration(
    graph: Graph, w: Weights | None = None, lam: dict[Edge, int] | None = None
) -> LayerSearchResult:
    started = perf_counter()
    nodes, edges = list(graph.nodes), list(set(graph.edges))
    max_span = max(lam.values(), default=1) if lam is not None else 1
    max_layers = max(1, len(nodes) * max_span)
    target = solve_fixed_layers(nodes, edges, max_layers, lam)
    solver_time = target.assignment.runtime
    target_count = target.torus_count
    if target_count is None:
        return LayerSearchResult(
            None, None, perf_counter() - started,
            solver_time=solver_time, solver_status=target.status,
        )

    best_layers, best = max_layers, target
    left, right = 1, max_layers
    while left <= right:
        mid = (left + right) // 2
        trial = solve_fixed_layers(nodes, edges, mid, lam)
        solver_time += trial.assignment.runtime
        if trial.torus_count is not None and trial.torus_count <= target_count:
            best_layers, best = mid, trial
            right = mid - 1
        else:
            left = mid + 1
    return LayerSearchResult(
        best_layers, best.torus_count, perf_counter() - started,
        solver_time=solver_time, solver_status=best.status,
    )
