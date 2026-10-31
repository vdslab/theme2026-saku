"""型付きの座標割当入口。"""

from collections import defaultdict, deque
from collections.abc import Mapping, Callable
from typing import TypedDict
import math
from statistics import median
from ..models import (
    Node,
    Edge,
    Layers,
    Positions,
    SubdividedGraph,
    CrossingResult,
    CoordinateResult,
)
from .periodic import (
    center_in_period,
    drawing_period,
    project_all_layers,
    smooth_torus_edges,
)
from .preparation import (
    complete_order,
    find_dummy_nodes,
    validate_graph,
    validate_parameters,
)
from .brandes_koepf import (
    align_to_narrowest,
    balanced_coordinates,
    map_node_layers,
    orient_order,
    single_bk_assignment,
)

MIN_NODE_GAP = 1.0
ALIGNMENT_ITERATIONS = 4


def compute_positions(
    order: Layers | None,
    layer_dict: Layers,
    edges: list[Edge],
    t_val: Mapping[Edge, bool] | None = None,
    psi: Mapping[Edge, float] | None = None,
    min_gap: float = MIN_NODE_GAP,
    smooth_iterations: int = ALIGNMENT_ITERATIONS,
    original_nodes: tuple[Node, ...] | None = None,
) -> Positions:
    """
    Compute node coordinates for the drawing stage.

    Args:
        order: dict[layer, list[node]], final in-layer order.
        layer_dict: dict[layer, list[node]], layered graph after dummy insertion.
        edges: list[(u, v)], edges after dummy insertion.
        t_val: dict[(u, v), bool], left-right torus flags.
        psi: dict[(u, v), int], top-bottom winding numbers.
        min_gap: minimum cyclic distance between consecutive nodes in one
            layer, including the last-to-first gap across the torus seam.
        smooth_iterations: ordered smoothing rounds after BK compaction.
        original_nodes: original (non-dummy) nodes.  If supplied, inner
            dummy-to-dummy segments are preferred when type-1 conflicts are
            marked, as in Brandes--Koepf.

    Returns:
        dict[node, (x, y)]: coordinates in the same drawing coordinate system as
        draw_radial_torus.  When ``min_gap`` is not 1, pass
        ``vertical_period=max_layer_size * min_gap`` to that drawing function.
    """
    validate_parameters(min_gap, smooth_iterations)
    t_val = {} if t_val is None else t_val
    psi = {} if psi is None else psi
    layers = sorted(layer_dict.keys())
    if not layers:
        return {}
    node_order = complete_order(order, layer_dict, layers)
    validate_graph(node_order, edges, psi)
    node_to_layer = map_node_layers(node_order)
    layer_index = {layer: index for index, layer in enumerate(layers)}
    period = drawing_period(node_order, min_gap)
    dummy_nodes = find_dummy_nodes(node_order, original_nodes)
    variants: list[dict[Node, float]] = []
    horizontal_directions: list[bool] = []
    for scan_forward in (True, False):
        for horizontal_forward in (True, False):
            oriented_order = orient_order(node_order, horizontal_forward)
            y_values = single_bk_assignment(
                node_order=oriented_order,
                edges=edges,
                t_val=t_val,
                psi=psi,
                layers=layers,
                node_to_layer=node_to_layer,
                layer_index=layer_index,
                scan_forward=scan_forward,
                min_gap=min_gap,
                dummy_nodes=dummy_nodes,
            )
            if not horizontal_forward:
                y_values = {node: -value for node, value in y_values.items()}
            variants.append(y_values)
            horizontal_directions.append(horizontal_forward)
    variants: list[dict[Node, float]] = align_to_narrowest(
        variants, horizontal_directions
    )
    y_by_node = balanced_coordinates(variants)
    y_by_node = center_in_period(y_by_node, period, min_gap)
    y_by_node = project_all_layers(y_by_node, node_order, period, min_gap)
    y_by_node = smooth_torus_edges(
        y_by_node=y_by_node,
        node_order=node_order,
        edges=edges,
        psi=psi,
        period=period,
        min_gap=min_gap,
        iterations=smooth_iterations,
    )
    x_min = -0.5
    pos: Positions = {}
    for layer in layers:
        x = x_min + layer_index[layer] + 0.5
        for node in node_order[layer]:
            pos[node] = (x, y_by_node[node])
    return pos


def assign_coordinates(
    graph: SubdividedGraph,
    crossing: CrossingResult,
    *,
    min_gap: float = 1.0,
    smooth_iterations: int = 4
) -> CoordinateResult:
    """元のBK系計算と、その計算に使用した周期を返す。"""
    positions = compute_positions(
        crossing.order,
        graph.layers,
        list(graph.graph.edges),
        graph.torus_flags,
        crossing.winding_numbers,
        min_gap,
        smooth_iterations,
        graph.original_nodes,
    )
    period = drawing_period(graph.layers, min_gap)
    return CoordinateResult(positions, period)
