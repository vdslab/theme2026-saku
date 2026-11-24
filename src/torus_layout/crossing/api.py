"""ダミー挿入済みの同じ入力に、現在の交差削減を適用する。"""

from .. import constants

from ..models import SubdividedGraph, CrossingResult, SeamMethod, SiftingMethod
from .global_sifting import sift_blocks
from .initialization import initial_orders
from .sifting import run_radial_sifting, run_sifting_with_global_guard
from .shortest import sift_with_shortest_windings
from .lib.embedding import (
    compute_winding_numbers,
    postprocess_sifting_rotations,
)
from .lib.crossings import count_all_crossings
from .joint_seam import optimize_joint_seam
from .seam import optimize_seam, seam_score
from .unwind import unwind_levels


def reduce_crossings(
    graph: SubdividedGraph,
    rounds: int = constants.DEFAULT_ROUNDS,
    *,
    optimize_seams: bool = constants.DEFAULT_OPTIMIZE_SEAMS,
    unwind: bool = constants.DEFAULT_UNWIND_LEVELS,
    sifting_method: SiftingMethod = constants.DEFAULT_SIFTING_METHOD,
    algo2: bool = constants.DEFAULT_ALGO2,
    prioritize_internal_seams: bool = False,
    seam_method: SeamMethod = constants.DEFAULT_SEAM_METHOD,
) -> CrossingResult:
    """Run the selected sifting method, optional rotation, UNWIND-LEVEL, and seam selection.

    Use parting with Algo2 enabled and both boundary options disabled to reproduce the legacy path.
    The seam optimizer requires a proper graph with cyclic adjacent-layer segments.
    With UNWIND and seam optimization enabled, joint mode requires zero
    internal seam segments. The legacy mode uses sequential UNWIND and DP.
    """
    if seam_method not in ("joint", "legacy"):
        raise ValueError(f"unknown seam method: {seam_method!r}")
    layers = sorted(graph.layers)
    edges = list(graph.graph.edges)
    order = initial_orders(graph.layers, layers, edges)[0]
    if sifting_method == "global":
        order, winding = sift_blocks(graph, order, layers, rounds)
    elif sifting_method == "shortest":
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
    if algo2:
        postprocess_sifting_rotations(order, winding, layers, edges)
    return _process_boundaries(
        graph, CrossingResult(order, winding), unwind, optimize_seams,
        prioritize_internal_seams, seam_method=seam_method,
    )


def _process_boundaries(
    graph: SubdividedGraph, embedding: CrossingResult, unwind: bool, optimize_seams: bool,
    prioritize_internal_seams: bool, *, seam_method: SeamMethod = constants.DEFAULT_SEAM_METHOD,
) -> CrossingResult:
    if seam_method == "joint" and unwind and optimize_seams:
        joint_result = optimize_joint_seam(graph, embedding)
        if joint_result is None:
            raise ValueError(
                "同時境界最適化ではダミー同士の境界通過を0本にできません。"
                "従来方式で続行するには --seam-method legacy を指定してください。"
            )
        return joint_result

    result = embedding
    if unwind:
        result = unwind_levels(graph, result)
    if not optimize_seams:
        return result
    early_unwind = result
    result = optimize_seam(graph, result, prioritize_internal=prioritize_internal_seams)
    if unwind:
        # A different cut can expose a common turn that was hidden beforehand.
        # Compare the new fallback before/after DP; retain the better result.
        inner_only = unwind_levels(graph, embedding, include_non_inner=False)
        cut_first = result if inner_only == early_unwind else optimize_seam(
            graph, inner_only, prioritize_internal=prioritize_internal_seams,
        )
        late_unwind = unwind_levels(graph, cut_first)
        candidate = (
            optimize_seam(graph, late_unwind, prioritize_internal=prioritize_internal_seams)
            if late_unwind != cut_first else cut_first
        )
        if seam_score(graph, candidate, prioritize_internal_seams) < seam_score(
            graph, result, prioritize_internal_seams,
        ):
            result = candidate
    return result


def count_crossings(graph: SubdividedGraph, crossing: CrossingResult) -> int:
    return count_all_crossings(
        crossing.order,
        crossing.winding_numbers,
        sorted(graph.layers),
        list(graph.graph.edges),
    )
