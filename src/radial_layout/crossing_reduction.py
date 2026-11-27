"""Crossing reduction for vertices arranged on concentric circles."""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from math import floor
from typing import Hashable, Iterable, TypeAlias

from layout_common.hierarchy import DummyNode, validate_proper_hierarchy

from . import constants

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
    """Apply Bachmaier (2007) §4.4 to consecutive pairs of levels."""
    if rounds < 1:
        raise ValueError("rounds must be positive")
    edge_list = tuple(dict.fromkeys(edges))
    order = {layer: list(nodes) for layer, nodes in sorted(layers.items())}
    node_layers = validate_proper_hierarchy(order, edge_list)
    boundaries = defaultdict(list)
    for edge in edge_list:
        boundaries[node_layers[edge[0]]].append(edge)
    # Section V-D contracts a singleton first level to the center. Its
    # segments are straight spokes, with zero crossings and no parting.
    if order and len(order[min(order)]) == 1:
        boundaries.pop(min(order), None)
    inner_boundaries = {layer: [edge for edge in boundary if _is_inner(edge)]
                        for layer, boundary in boundaries.items()}
    winding = dict.fromkeys(edge_list, 0)
    def score_boundary(layer):
        positions = {node: index for level in (layer, layer + 1)
                     for index, node in enumerate(order[level])}
        return (
            _count_boundary(inner_boundaries[layer], positions, winding),
            _count_boundary(boundaries[layer], positions, winding),
        )

    scores = {layer: score_boundary(layer) for layer in boundaries}
    if any(inner for inner, _ in scores.values()):
        _order_dummy_chains(order, inner_boundaries)
        scores = {layer: score_boundary(layer) for layer in boundaries}
    best = _copy_order(order)
    best_winding = winding.copy()
    best_score = (sum(inner for inner, _ in scores.values()),
                  sum(total for _, total in scores.values()))
    seen = set()
    for _ in range(rounds):
        state = tuple(tuple(nodes) for nodes in order.values()), tuple(winding.values())
        if state in seen:
            break
        seen.add(state)
        for downward in (True, False):
            dirty = set()
            levels = sorted(boundaries, reverse=not downward)
            for layer in levels:
                free_layer = layer + 1 if downward else layer
                previous_order = tuple(order[free_layer])
                previous_winding = [winding[edge] for edge in boundaries[layer]]
                if downward:
                    _sift_boundary(order[layer], order[layer + 1], boundaries[layer], winding)
                else:
                    reversed_edges = [(v, u) for u, v in boundaries[layer]]
                    reversed_winding = {(v, u): -winding[u, v] for u, v in boundaries[layer]}
                    _sift_boundary(order[layer + 1], order[layer], reversed_edges, reversed_winding)
                    winding.update({(v, u): -offset for (u, v), offset in reversed_winding.items()})
                if tuple(order[free_layer]) != previous_order:
                    dirty.update((free_layer - 1, free_layer))
                if any(winding[edge] != old for edge, old in zip(boundaries[layer], previous_winding)):
                    dirty.add(layer)
            for layer in dirty & boundaries.keys():
                scores[layer] = score_boundary(layer)
            current = (sum(inner for inner, _ in scores.values()),
                       sum(total for _, total in scores.values()))
            if current < best_score:
                best, best_winding, best_score = _copy_order(order), winding.copy(), current

    # Algorithm 2 averages the signed span. Use the span of Eq. (4) in our
    # counterclockwise angles: a clockwise rotation reduces it by r/n.
    for layer, boundary in sorted(boundaries.items()):
        balance_level_rotation(best, best_winding, layer + 1, boundary, boundaries.get(layer + 1, ()))

    frozen = {layer: tuple(nodes) for layer, nodes in best.items()}
    return RadialEmbedding(frozen, best_winding, best_score[1])


def _order_dummy_chains(order, inner_boundaries):
    """Seed a conflict-free order for callers supplying reordered dummy nodes."""
    predecessors = {}
    successors = set()
    for boundary in inner_boundaries.values():
        for u, v in boundary:
            if u in successors or v in predecessors:
                raise ValueError("inner segments must form vertex-disjoint dummy chains")
            successors.add(u)
            predecessors[v] = u

    chain_order = {}
    for layer, nodes in order.items():
        for node in nodes:
            if isinstance(node, DummyNode):
                chain_order[node] = (
                    chain_order[predecessors[node]] if node in predecessors else len(chain_order)
                )
        dummies = iter(sorted((node for node in nodes if node in chain_order), key=chain_order.__getitem__))
        order[layer] = [next(dummies) if node in chain_order else node for node in nodes]


def rotate_level(order, winding, layer, steps, incoming, outgoing):
    """Move the ray clockwise by steps, preserving the radial embedding."""
    nodes = order[layer]
    if not nodes or not steps:
        return
    size = len(nodes)
    turns, split = divmod(steps, size)
    moved = set(nodes[:split])
    order[layer] = nodes[split:] + nodes[:split]
    for edge in incoming:
        winding[edge] -= turns + (edge[1] in moved)
    for edge in outgoing:
        winding[edge] += turns + (edge[0] in moved)


def balance_level_rotation(order, winding, level, incoming, outgoing):
    """Rotate by the nearest position to the mean signed incoming span."""
    fixed, free = order[level - 1], order[level]
    fixed_pos = {node: i for i, node in enumerate(fixed)}
    free_pos = {node: i for i, node in enumerate(free)}
    span = sum(Fraction(free_pos[v], len(free)) - Fraction(fixed_pos[u], len(fixed))
               + winding[u, v] for u, v in incoming)
    rotation = floor(span * len(free) / len(incoming) + Fraction(1, 2))
    rotate_level(order, winding, level, rotation, incoming, outgoing)


def _is_inner(edge):
    return all(isinstance(node, DummyNode) for node in edge)


def _sift_boundary(fixed, free, edges, winding):
    """One round of Algorithm 1, with the §5.1.1 inner crossing weight."""
    fixed_pos = {node: i for i, node in enumerate(fixed)}
    moving_pos = {node: i for i, node in enumerate(free)}
    incident = defaultdict(list)
    for edge in edges:
        incident[edge[1]].append(edge)
    inner = {edge for edge in edges if _is_inner(edge)}

    def crossings(first, second):
        count = _crossings_from_signs(
            _sign(fixed_pos[second[0]] - fixed_pos[first[0]]),
            _sign(moving_pos[second[1]] - moving_pos[first[1]]),
            winding[second] - winding[first],
        )
        return count * len(edges) if first in inner and second in inner else count

    for node in tuple(free):
        moving = sorted(incident[node], key=lambda edge: fixed_pos[edge[0]])
        if not moving:
            continue
        free.remove(node)
        free.insert(0, node)
        moving_pos.update((member, i) for i, member in enumerate(free))
        for edge in moving:
            winding[edge] = 1
        best_position = 0
        best_offsets = [1] * len(moving)
        best_change = change = 0
        parting = 0

        for position in range(max(1, len(free) - 1)):
            while parting < 2 * len(moving):
                edge = moving[parting % len(moving)]
                before = sum(crossings(edge, other) for other in edges if other != edge)
                winding[edge] -= 1
                after = sum(crossings(edge, other) for other in edges if other != edge)
                if after > before:
                    winding[edge] += 1
                    break
                change += after - before
                parting += 1

            if change < best_change:
                best_position, best_change = position, change
                best_offsets = [winding[edge] for edge in moving]
            if position + 1 < len(free):
                successor = free[position + 1]
                change -= sum(crossings(a, b) for a in moving for b in incident[successor])
                free[position], free[position + 1] = successor, node
                moving_pos[successor], moving_pos[node] = position, position + 1
                change += sum(crossings(a, b) for a in moving for b in incident[successor])

        free.remove(node)
        free.insert(best_position, node)
        moving_pos.update((member, i) for i, member in enumerate(free))
        winding.update(zip(moving, best_offsets))


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
    """Count radial crossings, with zero offsets for an initial order."""

    normalized = {layer: tuple(nodes) for layer, nodes in order.items()}
    edge_list = tuple(dict.fromkeys(edges))
    node_layers = validate_proper_hierarchy(normalized, edge_list)
    if winding is None:
        winding = dict.fromkeys(edge_list, 0)
    positions = {node: index for nodes in normalized.values() for index, node in enumerate(nodes)}
    by_boundary: dict[int, list[Edge]] = defaultdict(list)
    for edge in edge_list:
        by_boundary[node_layers[edge[0]]].append(edge)

    return sum(_count_boundary(edges, positions, winding) for edges in by_boundary.values())


def _count_boundary(edges, positions, winding):
    return sum(_pair_crossings(first, second, positions, winding)
               for index, first in enumerate(edges) for second in edges[index + 1:])


def _pair_crossings(
    first: Edge,
    second: Edge,
    positions: dict[Node, int],
    winding: dict[Edge, int],
) -> int:
    source_sign = _sign(positions[second[0]] - positions[first[0]])
    target_sign = _sign(positions[second[1]] - positions[first[1]])
    winding_delta = winding[second] - winding[first]
    return _crossings_from_signs(source_sign, target_sign, winding_delta)


def _crossings_from_signs(source_sign: int, target_sign: int, delta: int) -> int:
    return max(0, (abs(2 * delta + target_sign - source_sign)
                   + abs(source_sign) + abs(target_sign) - 2) // 2)


def _copy_order(order: dict[int, list[Node]]) -> dict[int, list[Node]]:
    return {layer: list(nodes) for layer, nodes in order.items()}


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
