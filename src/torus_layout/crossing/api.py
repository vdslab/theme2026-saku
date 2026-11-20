"""ダミー挿入済みの同じ入力に、現在の交差削減を適用する。"""

from .. import constants

from ..models import SubdividedGraph, CrossingResult, SiftingMethod
from .initialization import initial_orders
from .sifting import run_radial_sifting, run_sifting_with_global_guard
from .shortest import sift_with_shortest_windings
from .lib.embedding import (
    copy_order,
    compute_winding_numbers,
    postprocess_sifting_rotations,
)
from .lib.crossings import count_all_crossings
from .seam import optimize_seam, count_seam_segments
from .unwind import unwind_levels


def reduce_crossings(
    graph: SubdividedGraph,
    rounds: int = constants.DEFAULT_ROUNDS,
    *,
    optimize_seams: bool = constants.DEFAULT_OPTIMIZE_SEAMS,
    unwind: bool = constants.DEFAULT_UNWIND_LEVELS,
    sifting_method: SiftingMethod = constants.DEFAULT_SIFTING_METHOD,
) -> CrossingResult:
    """Run radial-style sifting, guarded rotation, UNWIND-LEVEL, then seam selection.

    Use parting with both boundary options disabled to reproduce the legacy path.
    The seam optimizer requires a proper graph with cyclic adjacent-layer segments.
    """
    layers = sorted(graph.layers)
    edges = list(graph.graph.edges)
    order = initial_orders(graph.layers, layers, edges)[0]
    if sifting_method == "shortest":
        winding = sift_with_shortest_windings(order, layers, edges, rounds)
    elif sifting_method in ("radial", "parting"):
        winding = compute_winding_numbers(edges, order, graph.layers, layers)
        if sifting_method == "radial":
            run_radial_sifting(order, winding, layers, edges, rounds, dummy_nodes=graph.dummy_nodes)
        else:
            run_sifting_with_global_guard(
                order, winding, layers, edges, rounds, dummy_nodes=graph.dummy_nodes
            )
    else:
        raise ValueError(f"unknown sifting method: {sifting_method!r}")
    guarded_order = copy_order(order)
    guarded_winding = dict(winding)
    guarded_count = count_all_crossings(order, winding, layers, edges)
    postprocess_sifting_rotations(order, winding, layers, edges)
    if count_all_crossings(order, winding, layers, edges) > guarded_count:
        order = guarded_order
        winding = guarded_winding
    rotated = CrossingResult(order, winding)
    result = rotated
    if unwind:
        result = unwind_levels(graph, result)
    if not optimize_seams:
        return result
    early_unwind = result
    result = optimize_seam(graph, result)
    if unwind:
        # A different cut can expose a common turn that was hidden beforehand.
        # Compare the new fallback before/after DP; retain the better result.
        inner_only = unwind_levels(graph, rotated, include_non_inner=False)
        cut_first = result if inner_only == early_unwind else optimize_seam(graph, inner_only)
        late_unwind = unwind_levels(graph, cut_first)
        candidate = (
            optimize_seam(graph, late_unwind) if late_unwind != cut_first else cut_first
        )
        if count_seam_segments(graph, candidate) < count_seam_segments(graph, result):
            result = candidate
    return result


def count_crossings(graph: SubdividedGraph, crossing: CrossingResult) -> int:
    return count_all_crossings(
        crossing.order,
        crossing.winding_numbers,
        sorted(graph.layers),
        list(graph.graph.edges),
    )
