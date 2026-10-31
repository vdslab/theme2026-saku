"""既存の4手法を、同じデータ契約で選択する。"""
from collections.abc import Callable
from ..models import Node, Flags, Graph, Edge, Weights, BalanceMethod, LayerAssignmentResult, LayerSearchResult
from .balance.diff import _optimize_diff
from .balance.diff_square import _optimize_diff_square
from .balance.qp import _optimize_qp
from .balance.barycenter import _optimize_barycenter
from .search import find_minimum_configuration

type BalanceFunction = Callable[[list[Node], list[Edge], int, int, Weights, dict[Edge, int]], tuple[dict[Node, int], Flags, float]]

_METHODS: dict[str, BalanceFunction] = {"diff": _optimize_diff, "diff_square": _optimize_diff_square,
            "qp": _optimize_qp, "barycenter": _optimize_barycenter}

def balance_layers(graph: Graph, torus_count: int, layer_count: int,
                   method: BalanceMethod = "diff_square", *,
                   w: Weights | None = None,
                   lam: dict[Edge,int] | None = None) -> LayerAssignmentResult:
    edges = list(set(graph.edges))
    weights = {edge: 1 for edge in edges} if w is None else w
    spans = {edge: 1 for edge in edges} if lam is None else lam
    if method not in _METHODS:
        raise ValueError(f"Unknown func_type: {method}")
    return LayerAssignmentResult(*_METHODS[method](list(graph.nodes), edges, torus_count, layer_count, weights, spans))

def balance_diff(graph: Graph, torus_count: int, layer_count: int,
                 w: Weights | None = None, lam: dict[Edge,int] | None = None) -> LayerAssignmentResult:
    return balance_layers(graph, torus_count, layer_count, "diff", w=w, lam=lam)

def assign_layers(graph: Graph, method: BalanceMethod = "diff_square", *,
                  w: Weights | None = None, lam: dict[Edge,int] | None = None
                  ) -> tuple[LayerSearchResult, LayerAssignmentResult] | None:
    search = find_minimum_configuration(graph, w, lam)
    if search.layer_count is None or search.torus_count is None:
        return None
    assignment = balance_layers(graph, search.torus_count, search.layer_count, method, w=w, lam=lam)
    if not assignment.node_to_layer:
        return None
    return search, assignment
