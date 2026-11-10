"""ステップ4：Brandes--Köpf 法による平面座標の割当。

標準的な4種類の方向性を持つ割当を実装する。

1. 長辺の内部区間に関係する衝突を記録する。
2. 頂点を隣接頂点の中央値に揃える。
3. 得られた垂直ブロックを詰める。
4. 4方向の割当について中央2値の平均を取り、偏りを均す。

階層を左から右へ描画するため、元の上から下へ描く定式化で ``horizontal`` と
呼ばれる座標は、ここではレイヤー内の垂直座標になる。
"""

from . import constants

from collections import defaultdict
import math
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def assign_coordinates(
    layers: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    *,
    dummy_nodes: Iterable[Node] = (),
    node_gap: float = constants.DEFAULT_NODE_GAP,
    layer_gap: float = constants.DEFAULT_LAYER_GAP,
) -> dict[Node, tuple[float, float]]:
    """平面向けの Brandes--Köpf アルゴリズムで座標を割り当てる。"""

    if node_gap <= 0 or layer_gap <= 0:
        raise ValueError("node_gap と layer_gap は正の値である必要があります")

    node_order = {
        layer: tuple(nodes) for layer, nodes in sorted(layers.items())
    }
    edge_list = tuple(edges)
    node_to_layer = _validate_proper_hierarchy(node_order, edge_list)
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
            root, align = _vertical_alignment(
                oriented_order,
                edge_list,
                node_to_layer,
                conflicts,
                align_with_predecessors,
            )
            coordinates = _horizontal_compaction(
                oriented_order, root, align, node_gap
            )
            if not left_to_right:
                coordinates = {
                    node: -coordinate for node, coordinate in coordinates.items()
                }
            assignments.append(coordinates)
            horizontal_directions.append(left_to_right)

    assignments = _align_to_narrowest(assignments, horizontal_directions)
    within_layer = _average_median(assignments)
    center = (
        min(within_layer.values(), default=0.0)
        + max(within_layer.values(), default=0.0)
    ) / 2.0

    return {
        node: (layer * layer_gap, within_layer[node] - center)
        for layer, nodes in node_order.items()
        for node in nodes
    }


def _validate_proper_hierarchy(
    layers: dict[int, tuple[Node, ...]], edges: tuple[Edge, ...]
) -> dict[Node, int]:
    node_to_layer: dict[Node, int] = {}
    for layer, nodes in layers.items():
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"レイヤー {layer!r} に重複した頂点が含まれています")
        for node in nodes:
            if node in node_to_layer:
                raise ValueError(f"頂点 {node!r} が複数のレイヤーに存在します")
            node_to_layer[node] = layer

    for source, target in edges:
        if source not in node_to_layer or target not in node_to_layer:
            raise ValueError("すべての辺の端点が layers に含まれている必要があります")
        if node_to_layer[target] != node_to_layer[source] + 1:
            raise ValueError("Brandes--Köpf 法には正規化された階層が必要です")
    return node_to_layer


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
    node_to_layer: dict[Node, int],
    conflicts: set[Edge],
    align_with_predecessors: bool,
) -> tuple[dict[Node, Node], dict[Node, Node]]:
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
    return root, align


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
    align: dict[Node, Node],
    node_gap: float,
) -> dict[Node, float]:
    """Brandes--Köpf アルゴリズム3（ブロック圧縮）。"""

    nodes = [node for layer_nodes in layers.values() for node in layer_nodes]
    position = {
        node: index
        for layer_nodes in layers.values()
        for index, node in enumerate(layer_nodes)
    }
    predecessor = {
        node: layer_nodes[index - 1]
        for layer_nodes in layers.values()
        for index, node in enumerate(layer_nodes)
        if index > 0
    }
    sink = {node: node for node in nodes}
    shift = {node: math.inf for node in nodes}
    coordinate: dict[Node, float | None] = {node: None for node in nodes}

    def place_block(vertex: Node) -> None:
        if coordinate[vertex] is not None:
            return
        coordinate[vertex] = 0.0
        current = vertex
        while True:
            if position[current] > 0:
                previous_root = root[predecessor[current]]
                place_block(previous_root)
                if sink[vertex] == vertex:
                    sink[vertex] = sink[previous_root]
                if sink[vertex] != sink[previous_root]:
                    shift[sink[previous_root]] = min(
                        shift[sink[previous_root]],
                        float(coordinate[vertex])
                        - float(coordinate[previous_root])
                        - node_gap,
                    )
                else:
                    coordinate[vertex] = max(
                        float(coordinate[vertex]),
                        float(coordinate[previous_root]) + node_gap,
                    )
            current = align[current]
            if current == vertex:
                break

    for node in nodes:
        if root[node] == node:
            place_block(node)

    result: dict[Node, float] = {}
    for node in nodes:
        root_coordinate = float(coordinate[root[node]])
        class_shift = shift[sink[root[node]]]
        result[node] = (
            root_coordinate
            if math.isinf(class_shift)
            else root_coordinate + class_shift
        )
    return result


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
