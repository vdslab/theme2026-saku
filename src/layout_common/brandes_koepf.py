"""Four-direction Brandes–Köpf coordinates for a proper hierarchy."""

from collections import defaultdict
from typing import Hashable, Iterable, TypeAlias

import networkx as nx

from .hierarchy import validate_proper_hierarchy

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def assign_within_layer_coordinates(
    layers: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    *,
    dummy_nodes: Iterable[Node] = (),
    separation: dict[int, float],
) -> dict[Node, float]:
    """平面向けの Brandes--Köpf アルゴリズムで座標を割り当てる。"""

    node_order = {
        layer: tuple(nodes) for layer, nodes in sorted(layers.items())
    }
    edge_list = tuple(edges)
    node_to_layer = validate_proper_hierarchy(node_order, edge_list)
    dummy_set = set(dummy_nodes)
    unknown_dummies = dummy_set - set(node_to_layer)
    if unknown_dummies:
        raise ValueError("dummy_nodes に layers 内に存在しない頂点が含まれています")

    conflicts = _mark_inner_segment_conflicts(
        node_order, edge_list, node_to_layer, dummy_set
    )
    assignments: list[dict[Node, float]] = []
    horizontal_directions: list[bool] = []

    for align_with_predecessors in (True, False):
        for left_to_right in (True, False):
            oriented_order = _orient_order(node_order, left_to_right)
            if not align_with_predecessors:
                oriented_order = dict(reversed(oriented_order.items()))
            root = _vertical_alignment(
                oriented_order,
                edge_list,
                conflicts,
                align_with_predecessors,
            )
            coordinates = _horizontal_compaction(
                oriented_order, root, separation
            )
            if not left_to_right:
                coordinates = {
                    node: -coordinate for node, coordinate in coordinates.items()
                }
            assignments.append(coordinates)
            horizontal_directions.append(left_to_right)

    assignments = _align_to_narrowest(assignments, horizontal_directions)
    return _average_median(assignments)


def _mark_inner_segment_conflicts(
    layers: dict[int, tuple[Node, ...]],
    edges: tuple[Edge, ...],
    node_to_layer: dict[Node, int],
    dummy_nodes: set[Node],
) -> set[Edge]:
    """内部区間と交差する非内部区間を記録する（タイプ1の衝突）。"""

    position = {
        node: index
        for nodes in layers.values()
        for index, node in enumerate(nodes)
    }
    by_boundary: dict[int, list[Edge]] = defaultdict(list)
    for edge in edges:
        by_boundary[node_to_layer[edge[0]]].append(edge)

    conflicts: set[Edge] = set()
    for boundary_edges in by_boundary.values():
        inner_edges = [
            edge
            for edge in boundary_edges
            if edge[0] in dummy_nodes and edge[1] in dummy_nodes
        ]
        for edge in boundary_edges:
            if edge in inner_edges:
                continue
            for inner_edge in inner_edges:
                if _segments_cross(edge, inner_edge, position):
                    conflicts.add(edge)
                    break
    return conflicts


def _segments_cross(
    first: Edge, second: Edge, position: dict[Node, int]
) -> bool:
    if first[0] == second[0] or first[1] == second[1]:
        return False
    upper_delta = position[first[0]] - position[second[0]]
    lower_delta = position[first[1]] - position[second[1]]
    return upper_delta * lower_delta < 0


def _orient_order(
    layers: dict[int, tuple[Node, ...]], left_to_right: bool
) -> dict[int, tuple[Node, ...]]:
    if left_to_right:
        return dict(layers)
    return {layer: tuple(reversed(nodes)) for layer, nodes in layers.items()}


def _vertical_alignment(
    layers: dict[int, tuple[Node, ...]],
    edges: tuple[Edge, ...],
    conflicts: set[Edge],
    align_with_predecessors: bool,
) -> dict[Node, Node]:
    """Brandes--Köpf アルゴリズム2を、一方の垂直方向に適用する。"""

    nodes = [node for layer_nodes in layers.values() for node in layer_nodes]
    root = {node: node for node in nodes}
    align = {node: node for node in nodes}
    position = {
        node: index
        for layer_nodes in layers.values()
        for index, node in enumerate(layer_nodes)
    }
    incoming: dict[Node, list[Node]] = defaultdict(list)
    outgoing: dict[Node, list[Node]] = defaultdict(list)
    for source, target in edges:
        outgoing[source].append(target)
        incoming[target].append(source)

    layer_ids = sorted(layers)
    scanned_layers = (
        layer_ids[1:]
        if align_with_predecessors
        else list(reversed(layer_ids[:-1]))
    )

    for layer in scanned_layers:
        last_aligned_position = -1
        for node in layers[layer]:
            neighbors = (
                incoming.get(node, [])
                if align_with_predecessors
                else outgoing.get(node, [])
            )
            neighbors = sorted(neighbors, key=position.__getitem__)
            for neighbor in _median_neighbors(neighbors):
                edge = (
                    (neighbor, node)
                    if align_with_predecessors
                    else (node, neighbor)
                )
                if (
                    align[node] == node
                    and edge not in conflicts
                    and last_aligned_position < position[neighbor]
                ):
                    align[neighbor] = node
                    root[node] = root[neighbor]
                    align[node] = root[node]
                    last_aligned_position = position[neighbor]
    return root


def _median_neighbors(neighbors: list[Node]) -> tuple[Node, ...]:
    if not neighbors:
        return ()
    left = (len(neighbors) - 1) // 2
    right = len(neighbors) // 2
    if left == right:
        return (neighbors[left],)
    return (neighbors[left], neighbors[right])


def _horizontal_compaction(
    layers: dict[int, tuple[Node, ...]],
    root: dict[Node, Node],
    separation: dict[int, float],
) -> dict[Node, float]:
    """Compact alignment blocks with the separation of each level."""
    blocks = nx.DiGraph()
    blocks.add_nodes_from(root.values())
    for layer, nodes in layers.items():
        for left, right in zip(nodes, nodes[1:]):
            a, b = root[left], root[right]
            old_gap = blocks.get_edge_data(a, b, {}).get("gap", 0.0)
            blocks.add_edge(a, b, gap=max(old_gap, separation[layer]))

    topological = tuple(nx.topological_sort(blocks))
    coordinates = {}
    for block in topological:
        coordinates[block] = max(
            (coordinates[pred] + data["gap"] for pred, data in blocks.pred[block].items()),
            default=0.0,
        )

    # Each class is the set reachable from its first block after earlier
    # classes have been removed. Compact each class against the earlier classes.
    class_id = {}
    classes = []
    for block in root.values():
        if block in class_id:
            continue
        members = [block]
        class_id[block] = len(classes)
        for member in members:
            for successor in blocks[member]:
                if successor not in class_id:
                    class_id[successor] = len(classes)
                    members.append(successor)
        classes.append(members)

    for index, members in enumerate(classes):
        shift = min(
            (coordinates[right] - coordinates[left] - data["gap"]
             for left in members
             for right, data in blocks[left].items()
             if class_id[right] != index),
            default=0.0,
        )
        for block in members:
            coordinates[block] += shift
    return {node: coordinates[block] for node, block in root.items()}


def _align_to_narrowest(
    assignments: list[dict[Node, float]],
    horizontal_directions: list[bool],
) -> list[dict[Node, float]]:
    bounds = []
    for assignment in assignments:
        values = list(assignment.values())
        lower = min(values, default=0.0)
        upper = max(values, default=0.0)
        bounds.append((lower, upper, upper - lower))

    reference_index = min(range(len(assignments)), key=lambda i: bounds[i][2])
    reference_lower, reference_upper, _ = bounds[reference_index]
    aligned = []
    for assignment, left_to_right, (lower, upper, _) in zip(
        assignments, horizontal_directions, bounds
    ):
        shift = (
            reference_lower - lower
            if left_to_right
            else reference_upper - upper
        )
        aligned.append(
            {node: value + shift for node, value in assignment.items()}
        )
    return aligned


def _average_median(
    assignments: list[dict[Node, float]],
) -> dict[Node, float]:
    if not assignments:
        return {}
    return {
        node: sum(sorted(assignment[node] for assignment in assignments)[1:3])
        / 2.0
        for node in assignments[0]
    }
