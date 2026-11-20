"""Two-phase n-level barycentric crossing reduction (Sugiyama et al., §III)."""

from collections import defaultdict
from fractions import Fraction
from typing import Hashable, Iterable, TypeAlias

from . import constants

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def reduce_crossings(
    layers: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    sweeps: int = constants.DEFAULT_CROSSING_SWEEPS,
) -> dict[int, tuple[Node, ...]]:
    """Repeat stable BC sweeps and reverse equal-barycenter groups in Phase 2."""
    if sweeps < 1:
        raise ValueError("sweeps must be positive")
    order = {layer: tuple(nodes) for layer, nodes in sorted(layers.items())}
    edge_list = tuple(dict.fromkeys(edges))
    best = order.copy()
    best_crossings = count_crossings(best, edge_list)
    if len(order) < 2:
        return best

    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for source, target in edge_list:
        incoming[target].append(source)
        outgoing[source].append(target)
    levels = list(order)
    directions = ((levels[1:], incoming, -1), (levels[-2::-1], outgoing, 1))

    def remember():
        nonlocal best, best_crossings
        crossings = count_crossings(order, edge_list)
        if crossings < best_crossings:
            best, best_crossings = order.copy(), crossings

    def matrix_signature():
        # The occupied entries of the adjacency matrices, in order.
        positions = {node: (level, index) for level, nodes in order.items()
                     for index, node in enumerate(nodes)}
        return tuple(sorted((positions[u], positions[v]) for u, v in edge_list))

    def phase_one(first_direction):
        seen = {matrix_signature()}
        for _ in range(sweeps):
            for direction in (first_direction, 1 - first_direction):
                visited, neighbors, offset = directions[direction]
                for level in visited:
                    order[level] = _barycentric_order(order[level], order.get(level + offset, ()), neighbors)
                remember()
            state = matrix_signature()
            if state in seen:
                break
            seen.add(state)
        return 1 - first_direction

    if len(levels) == 2:
        upper, lower = levels
        # Follow the two-level example (M0–M5): rows first, then columns.
        phase_one(1)
        for _ in range(sweeps):
            for level, reference, neighbors, opposite in (
                (lower, upper, incoming, outgoing),
                (upper, lower, outgoing, incoming),
            ):
                order[level] = _barycentric_order(
                    order[level], order[reference], neighbors, reverse_ties=True
                )
                if order[reference] != _barycentric_order(
                    order[reference], order[level], opposite
                ):
                    phase_one(1)
                    break
            else:
                break
        return best

    direction = phase_one(0)
    seen = set()
    for _ in range(sweeps):
        state = direction, matrix_signature()
        if state in seen:
            break
        seen.add(state)
        for phase_direction in (direction, 1 - direction):
            visited, neighbors, offset = directions[phase_direction]
            for level in visited:
                reordered = _barycentric_order(
                    order[level], order.get(level + offset, ()), neighbors, reverse_ties=True
                )
                if reordered != order[level]:
                    order[level] = reordered
                    remember()
                    phase_one(phase_direction)
    return best


def _barycentric_order(nodes, reference, neighbors, *, reverse_ties=False):
    positions = {node: index for index, node in enumerate(reference, start=1)}
    active = [node for node in nodes if neighbors[node]]
    barycenter = {
        node: Fraction(sum(positions[v] for v in neighbors[node]), len(neighbors[node]))
        for node in active
    }
    if reverse_ties:
        # Phase 2 retains the order of the groups and reverses each group.
        groups = defaultdict(list)
        for node in active:
            groups[barycenter[node]].append(node)
        active = [groups[barycenter[node]].pop() for node in active]
    else:
        active.sort(key=barycenter.__getitem__)
    replacement = iter(active)
    return tuple(next(replacement) if node in barycenter else node for node in nodes)


def count_crossings(
    layers: dict[int, Iterable[Node]], edges: Iterable[Edge]
) -> int:
    """隣接する各レイヤー間にある辺の交差数を数える。"""

    positions = {
        node: (layer, index)
        for layer, nodes in layers.items()
        for index, node in enumerate(nodes)
    }
    by_boundary: dict[int, list[Edge]] = defaultdict(list)
    for source, target in edges:
        source_layer, _ = positions[source]
        target_layer, _ = positions[target]
        if target_layer != source_layer + 1:
            raise ValueError("交差数の計算には正規化された階層が必要です")
        by_boundary[source_layer].append((source, target))

    total = 0
    for boundary_edges in by_boundary.values():
        for index, (u1, v1) in enumerate(boundary_edges):
            for u2, v2 in boundary_edges[index + 1 :]:
                if u1 == u2 or v1 == v2:
                    continue
                upper_delta = positions[u1][1] - positions[u2][1]
                lower_delta = positions[v1][1] - positions[v2][1]
                total += upper_delta * lower_delta < 0
    return total
