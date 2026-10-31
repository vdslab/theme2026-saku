"""公開入力を従来のILPの引数へ変換する。"""
from ..models import Graph, Edge, Weights, LayerAssignmentResult
from .balance.diff import _optimize_diff

def balance_diff(graph: Graph, torus_count: int, layer_count: int,
                 w: Weights | None = None, lam: dict[Edge, int] | None = None) -> LayerAssignmentResult:
    edges = list(set(graph.edges))
    weights = {edge: 1 for edge in edges} if w is None else w
    spans = {edge: 1 for edge in edges} if lam is None else lam
    return LayerAssignmentResult(*_optimize_diff(list(graph.nodes), edges, torus_count, layer_count, weights, spans))
