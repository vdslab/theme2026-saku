"""ダミー挿入済みの同じ入力に、現在の交差削減を適用する。"""
from ..models import SubdividedGraph, CrossingResult
from .initialization import initial_orders
from .sifting import run_sifting_with_global_guard
from .lib.embedding import copy_order, compute_winding_numbers, postprocess_sifting_rotations
from .lib.crossings import count_all_crossings

def reduce_crossings(graph: SubdividedGraph, rounds: int = 5) -> CrossingResult:
    layers = sorted(graph.layers)
    edges = list(graph.graph.edges)
    order = initial_orders(graph.layers, layers, edges)[0]
    winding = compute_winding_numbers(edges, order, graph.layers, layers)
    run_sifting_with_global_guard(order, winding, layers, edges, rounds,
                                  dummy_nodes=graph.dummy_nodes)
    guarded_order = copy_order(order)
    guarded_winding = dict(winding)
    guarded_count = count_all_crossings(order, winding, layers, edges)
    postprocess_sifting_rotations(order, winding, layers, edges)
    if count_all_crossings(order, winding, layers, edges) > guarded_count:
        order = guarded_order
        winding = guarded_winding
    return CrossingResult(order, winding)

def count_crossings(graph: SubdividedGraph, crossing: CrossingResult) -> int:
    return count_all_crossings(crossing.order, crossing.winding_numbers,
                               sorted(graph.layers), list(graph.graph.edges))
