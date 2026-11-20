"""Priority layout (PR), Sugiyama, Tagawa and Toda (1981), §IV-B."""

from collections import defaultdict
from collections.abc import Hashable, Iterable
from fractions import Fraction

from layout_common.hierarchy import validate_proper_hierarchy

from . import constants

Node = Hashable
Edge = tuple[Node, Node]


def assign_coordinates(
    layers: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    *,
    dummy_nodes: Iterable[Node] = (),
    node_gap: float = constants.DEFAULT_NODE_GAP,
    layer_gap: float = constants.DEFAULT_LAYER_GAP,
    final_down_start: int = 2,
) -> dict[Node, tuple[float, float]]:
    """Apply DOWN, UP, then DOWN from paper level `final_down_start`."""
    if node_gap <= 0 or layer_gap <= 0 or final_down_start < 2:
        raise ValueError("positive gaps and final_down_start >= 2 are required")
    order = {layer: tuple(nodes) for layer, nodes in sorted(layers.items())}
    edges = tuple(dict.fromkeys(edges))
    node_layers = validate_proper_hierarchy(order, edges)
    dummies = set(dummy_nodes)
    if not dummies <= node_layers.keys():
        raise ValueError("dummy nodes must belong to the hierarchy")

    above = defaultdict(list)
    below = defaultdict(list)
    for source, target in edges:
        above[target].append(source)
        below[source].append(target)
    positions = {
        node: index for nodes in order.values() for index, node in enumerate(nodes, start=1)
    }
    levels = list(order)
    for visited, neighbors in (
        (levels[1:], above),
        (levels[-2::-1], below),
        (levels[final_down_start - 1:], above),
    ):
        for level in visited:
            _improve_level(order[level], positions, neighbors, dummies)
    return {
        node: (node_layers[node] * layer_gap, position * node_gap)
        for node, position in positions.items()
    }


def _improve_level(nodes, positions, neighbors, dummies):
    priority = [(node in dummies, len(neighbors[node]) if node not in dummies else 0)
                for node in nodes]
    for index in sorted(range(len(nodes)), key=priority.__getitem__, reverse=True):
        node = nodes[index]
        adjacent = neighbors[node]
        if not adjacent:
            continue
        target = round(Fraction(sum(positions[v] for v in adjacent), len(adjacent)))
        old = positions[node]
        if target == old:
            continue
        direction = 1 if target > old else -1
        movable = []
        for other in range(index + direction, len(nodes) if direction > 0 else -1, direction):
            if priority[other] >= priority[index]:
                limit = positions[nodes[other]] - (other - index)
                target = min(target, limit) if direction > 0 else max(target, limit)
                break
            movable.append(other)
        positions[node] = target
        for other in movable:
            neighbor = nodes[other]
            limit = target + (other - index)
            positions[neighbor] = (
                max(positions[neighbor], limit) if direction > 0
                else min(positions[neighbor], limit)
            )
