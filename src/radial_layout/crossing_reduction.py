"""Crossing reduction for vertices arranged on concentric circles."""

from . import constants

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


@dataclass(frozen=True)
class RadialEmbedding:
    order: dict[int, tuple[Node, ...]]
    winding: dict[Edge, int]
    crossings: int


def reduce_crossings(
    layers: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    *,
    rounds: int = constants.DEFAULT_ROUNDS,
) -> RadialEmbedding:
    """Optimize cyclic layer orders using circular barycenters and sifting."""

    if rounds < 1:
        raise ValueError("rounds must be positive")
    edge_list = tuple(edges)
    order = {layer: list(nodes) for layer, nodes in sorted(layers.items())}
    _validate_proper_hierarchy(order, edge_list)

    incoming: dict[Node, list[Node]] = defaultdict(list)
    outgoing: dict[Node, list[Node]] = defaultdict(list)
    for source, target in edge_list:
        outgoing[source].append(target)
        incoming[target].append(source)

    best = _copy_order(order)
    best_crossings = count_crossings(best, edge_list)
    layer_ids = sorted(order)
    for _ in range(rounds):
        for downward in (True, False):
            visited = layer_ids[1:] if downward else list(reversed(layer_ids[:-1]))
            neighbors = incoming if downward else outgoing
            reference_offset = -1 if downward else 1
            for layer in visited:
                reference = order[layer + reference_offset]
                _circular_barycenter_sort(order[layer], reference, neighbors)
                _choose_best_rotation(order, edge_list, layer)
                _sift_layer(order, edge_list, layer)
                crossings = count_crossings(order, edge_list)
                if crossings < best_crossings:
                    best = _copy_order(order)
                    best_crossings = crossings
        order = _copy_order(best)

    frozen = {layer: tuple(nodes) for layer, nodes in best.items()}
    winding = assign_winding_numbers(frozen, edge_list)
    return RadialEmbedding(frozen, winding, best_crossings)


def assign_winding_numbers(
    order: dict[int, Iterable[Node]], edges: Iterable[Edge]
) -> dict[Edge, int]:
    """Choose the shortest angular route (-1, 0, or +1) for each segment."""

    normalized = {layer: tuple(nodes) for layer, nodes in order.items()}
    locations = {
        node: (layer, index, len(nodes))
        for layer, nodes in normalized.items()
        for index, node in enumerate(nodes)
    }
    winding: dict[Edge, int] = {}
    for edge in edges:
        source, target = edge
        source_layer, source_index, source_count = locations[source]
        target_layer, target_index, target_count = locations[target]
        if target_layer != source_layer + 1:
            raise ValueError("winding assignment requires a proper hierarchy")
        source_turn = source_index / source_count
        target_turn = target_index / target_count
        difference = target_turn - source_turn
        winding[edge] = -1 if difference > 0.5 else 1 if difference < -0.5 else 0
    return winding


def count_crossings(
    order: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    winding: dict[Edge, int] | None = None,
) -> int:
    """Count radial edge crossings from cyclic orders and winding numbers."""

    normalized = {layer: tuple(nodes) for layer, nodes in order.items()}
    edge_list = tuple(edges)
    _validate_proper_hierarchy(normalized, edge_list)
    if winding is None:
        winding = assign_winding_numbers(normalized, edge_list)
    positions = {
        node: (layer, index)
        for layer, nodes in normalized.items()
        for index, node in enumerate(nodes)
    }
    by_boundary: dict[int, list[Edge]] = defaultdict(list)
    for edge in edge_list:
        by_boundary[positions[edge[0]][0]].append(edge)

    total = 0
    for boundary_edges in by_boundary.values():
        for index, first in enumerate(boundary_edges):
            for second in boundary_edges[index + 1 :]:
                total += _pair_crossings(first, second, positions, winding)
    return total


def _pair_crossings(
    first: Edge,
    second: Edge,
    positions: dict[Node, tuple[int, int]],
    winding: dict[Edge, int],
) -> int:
    source_sign = _sign(positions[second[0]][1] - positions[first[0]][1])
    target_sign = _sign(positions[second[1]][1] - positions[first[1]][1])
    winding_delta = winding[second] - winding[first]
    value = (
        abs(winding_delta + (target_sign - source_sign) / 2)
        + (abs(source_sign) + abs(target_sign)) / 2
        - 1
    )
    return max(0, int(round(value)))


def _circular_barycenter_sort(
    free_nodes: list[Node],
    fixed_nodes: list[Node],
    neighbors: dict[Node, list[Node]],
) -> None:
    if len(free_nodes) < 2 or not fixed_nodes:
        return
    free_count = len(free_nodes)
    fixed_count = len(fixed_nodes)
    fixed_position = {node: index for index, node in enumerate(fixed_nodes)}
    old_position = {node: index for index, node in enumerate(free_nodes)}

    def angle(node: Node) -> tuple[float, int]:
        neighbor_positions = [
            fixed_position[neighbor]
            for neighbor in neighbors[node]
            if neighbor in fixed_position
        ]
        if not neighbor_positions:
            return (2 * math.pi * old_position[node] / free_count, old_position[node])
        x = sum(
            math.cos(2 * math.pi * position / fixed_count)
            for position in neighbor_positions
        )
        y = sum(
            math.sin(2 * math.pi * position / fixed_count)
            for position in neighbor_positions
        )
        circular_angle = math.atan2(y, x) % (2 * math.pi)
        return (circular_angle, old_position[node])

    free_nodes.sort(key=angle)


def _choose_best_rotation(
    order: dict[int, list[Node]], edges: tuple[Edge, ...], layer: int
) -> None:
    nodes = order[layer]
    if len(nodes) < 2:
        return
    best = list(nodes)
    best_crossings = count_crossings(order, edges)
    for shift in range(1, len(nodes)):
        candidate = nodes[shift:] + nodes[:shift]
        order[layer] = candidate
        crossings = count_crossings(order, edges)
        if crossings < best_crossings:
            best = list(candidate)
            best_crossings = crossings
    order[layer] = best


def _sift_layer(
    order: dict[int, list[Node]], edges: tuple[Edge, ...], layer: int
) -> None:
    if len(order[layer]) < 2:
        return
    for node in tuple(order[layer]):
        current = list(order[layer])
        current.remove(node)
        best = list(order[layer])
        best_crossings = count_crossings(order, edges)
        for position in range(len(current) + 1):
            candidate = list(current)
            candidate.insert(position, node)
            order[layer] = candidate
            crossings = count_crossings(order, edges)
            if crossings < best_crossings:
                best = candidate
                best_crossings = crossings
        order[layer] = best


def _validate_proper_hierarchy(
    layers: dict[int, Iterable[Node]], edges: tuple[Edge, ...]
) -> None:
    node_to_layer: dict[Node, int] = {}
    for layer, nodes_iterable in layers.items():
        nodes = tuple(nodes_iterable)
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"layer {layer!r} contains duplicate vertices")
        for node in nodes:
            if node in node_to_layer:
                raise ValueError(f"vertex {node!r} occurs in multiple layers")
            node_to_layer[node] = layer
    for source, target in edges:
        if source not in node_to_layer or target not in node_to_layer:
            raise ValueError("every edge endpoint must occur in layers")
        if node_to_layer[target] != node_to_layer[source] + 1:
            raise ValueError("radial crossing reduction requires a proper hierarchy")


def _copy_order(order: dict[int, list[Node]]) -> dict[int, list[Node]]:
    return {layer: list(nodes) for layer, nodes in order.items()}


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
