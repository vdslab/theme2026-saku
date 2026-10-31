"""元と同じ入力検証と順序の補完。"""

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


def complete_order(
    order: Layers | None, layer_dict: Layers, layers: list[int]
) -> Layers:
    order = {} if order is None else order
    unknown_layers = [
        layer for layer, nodes in order.items() if layer not in layer_dict and nodes
    ]
    if unknown_layers:
        raise ValueError(f"order contains unknown layers: {unknown_layers!r}")
    completed: Layers = {}
    for layer in layers:
        layer_nodes = layer_dict[layer]
        seen: set[Node] = set()
        nodes: list[Node] = []
        for node in order.get(layer, []):
            if node not in layer_nodes:
                raise ValueError(
                    f"node {node!r} in order[{layer!r}] is absent from that layer"
                )
            if node in seen:
                raise ValueError(f"order[{layer!r}] contains duplicate node {node!r}")
            nodes.append(node)
            seen.add(node)
        for node in layer_nodes:
            if node not in seen:
                nodes.append(node)
        completed[layer] = nodes
    return completed


def validate_parameters(min_gap: float, smooth_iterations: int) -> None:
    if not isinstance(min_gap, (int, float)) or not math.isfinite(min_gap):
        raise ValueError("min_gap must be a finite number")
    if min_gap <= 0:
        raise ValueError("min_gap must be greater than zero")
    if isinstance(smooth_iterations, bool) or not isinstance(smooth_iterations, int):
        raise ValueError("smooth_iterations must be a non-negative integer")
    if smooth_iterations < 0:
        raise ValueError("smooth_iterations must be a non-negative integer")


def validate_graph(
    node_order: Layers, edges: list[Edge], psi: Mapping[Edge, float]
) -> None:
    node_to_layer: dict[Node, int] = {}
    for layer, nodes in node_order.items():
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"layer {layer!r} contains duplicate nodes")
        for node in nodes:
            if node in node_to_layer:
                raise ValueError(
                    f"node {node!r} occurs in both layer {node_to_layer[node]!r} and layer {layer!r}"
                )
            node_to_layer[node] = layer
    for edge in edges:
        if not isinstance(edge, tuple) or len(edge) != 2:
            raise ValueError(f"invalid edge: {edge!r}")
        if edge[0] not in node_to_layer or edge[1] not in node_to_layer:
            raise ValueError(f"edge endpoint is missing from layer_dict: {edge!r}")
        winding = psi.get(edge, 0)
        if not isinstance(winding, (int, float)) or not math.isfinite(winding):
            raise ValueError(f"psi must contain finite numeric values: {edge!r}")


def find_dummy_nodes(
    node_order: Layers, original_nodes: tuple[Node, ...] | None
) -> set[Node]:
    if original_nodes is None:
        return set()
    all_nodes = {node for nodes in node_order.values() for node in nodes}
    original_set = set(original_nodes)
    unknown = original_set - all_nodes
    if unknown:
        raise ValueError(
            f"original_nodes contains nodes that are absent from layer_dict: {sorted(unknown, key=repr)!r}"
        )
    return all_nodes - original_set
