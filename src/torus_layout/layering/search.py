"""元実装と同じ上限・判定でレイヤー数を二分探索する。"""
import time
from ..models import Graph, Node, Edge, Weights, LayerSearchResult
from .minimize_wraps import minimize_torus_edges

def find_minimum_torus_configuration(V: list[Node], A: list[Edge], w: Weights | None=None, lam: dict[Edge, int] | None=None) -> tuple[int | None, int | None, float]:
    st = time.time()
    edges = list(set(A))
    max_lam = max(lam.values(), default=1) if lam is not None else 1
    max_L = max(1, len(V) * max_lam)
    _, _, _, _, target_min_torus = minimize_torus_edges(V, edges, max_L, w, lam)
    if target_min_torus is None:
        return (None, None, time.time() - st)
    left, right = (1, max_L)
    optimal_L = max_L
    min_torus_count = target_min_torus
    while left <= right:
        mid = (left + right) // 2
        _, _, _, _, torus_count = minimize_torus_edges(V, edges, mid, w, lam)
        if torus_count is None:
            left = mid + 1
            continue
        if torus_count <= target_min_torus:
            optimal_L = mid
            min_torus_count = torus_count
            right = mid - 1
        else:
            left = mid + 1
    ed = time.time()
    return (optimal_L, min_torus_count, ed - st)

def find_minimum_configuration(
    graph: Graph, w: Weights | None = None, lam: dict[Edge, int] | None = None
) -> LayerSearchResult:
    return LayerSearchResult(*find_minimum_torus_configuration(list(graph.nodes), list(graph.edges), w, lam))
