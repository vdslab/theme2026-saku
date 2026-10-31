"""円形重心による初期順序。"""
import math
from collections import defaultdict
from ..models import Node, Edge, Layers
from .lib.embedding import base_order, copy_order

def initial_orders(L: Layers, layers: list[int], edges: list[Edge]) -> list[Layers]:
    """
    siftingの開始点に使うbarycenter初期解を作る。

    Args:
        L: ダミー挿入後のレイヤー辞書。
        layers: レイヤーキー列。
        edges: ダミー挿入後のエッジ集合。

    Returns:
        list[dict]: 初期order候補。
    """
    base = base_order(L, layers)
    return [barycentric_order(base, layers, edges)]

def barycentric_order(initial_order: Layers, layers: list[int], edges: list[Edge]) -> Layers:
    """
    初期順序にbarycenter sweepを複数回かける。

    Args:
        initial_order: sweep前のorder。
        layers: レイヤーキー列。
        edges: エッジ集合。

    Returns:
        dict: barycenterで整えたorder。
    """
    order = copy_order(initial_order)
    barycenter_sweep(order, layers, edges, forward=True)
    return order

def barycenter_sweep(order: Layers, layers: list[int], edges: list[Edge], forward: bool) -> None:
    """
    一方向に隣接レイヤーのbarycenter並べ替えを行う。

    Args:
        order: 更新対象のorder。
        layers: レイヤーキー列。
        edges: エッジ集合。
        forward: Trueなら左から右、Falseなら右から左にsweepする。

    Returns:
        None: orderを破壊的に更新する。
    """
    layer_indices = range(len(layers)) if forward else range(len(layers) - 1, -1, -1)
    for i in layer_indices:
        if forward:
            fixed_layer = layers[i]
            free_layer = layers[(i + 1) % len(layers)]
        else:
            free_layer = layers[i]
            fixed_layer = layers[(i + 1) % len(layers)]
        process_layer_pair(fixed_layer, free_layer, order, edges, fixed_is_source=forward)

def process_layer_pair(fixed_key: int, free_key: int, order: Layers, edges: list[Edge], fixed_is_source: bool=True) -> None:
    """
    固定レイヤーに対する自由レイヤーのbarycenter順序を計算する。

    Args:
        fixed_key: 固定するレイヤーキー。
        free_key: 並べ替えるレイヤーキー。
        order: 更新対象のorder。
        edges: エッジ集合。
        fixed_is_source: Trueなら fixed -> free の辺を見る。

    Returns:
        None: order[free_key]を破壊的に更新する。
    """
    fixed_nodes = order[fixed_key]
    free_nodes = order[free_key]
    if not fixed_nodes:
        return
    neighbors = neighbors_from_fixed_layer(fixed_nodes, free_nodes, edges, fixed_is_source)
    fixed_positions = circular_positions(fixed_nodes)
    fixed_angles = {node: 2 * math.pi * index / len(fixed_nodes) for index, node in enumerate(fixed_nodes)}
    order[free_key] = sorted(free_nodes, key=lambda node: barycenter_angle(node, free_nodes, neighbors, fixed_positions, fixed_angles))

def neighbors_from_fixed_layer(fixed_nodes: list[Node], free_nodes: list[Node], edges: list[Edge], fixed_is_source: bool) -> dict[Node, list[Node]]:
    """
    自由レイヤーの各ノードから固定レイヤー側の隣接ノードを集める。

    Args:
        fixed_nodes: 固定レイヤーのノード列。
        free_nodes: 自由レイヤーのノード列。
        edges: エッジ集合。
        fixed_is_source: Trueなら fixed -> free の辺を見る。

    Returns:
        dict: free_node -> list[fixed_node]。
    """
    fixed_set = set(fixed_nodes)
    free_set = set(free_nodes)
    neighbors: dict[Node, list[Node]] = defaultdict(list)
    for u, v in edges:
        if fixed_is_source and u in fixed_set and (v in free_set):
            neighbors[v].append(u)
        elif not fixed_is_source and u in free_set and (v in fixed_set):
            neighbors[u].append(v)
    return neighbors

def circular_positions(nodes: list[Node]) -> dict[Node, tuple[float, float]]:
    """
    ノード列を単位円上に等間隔配置した座標を返す。

    Args:
        nodes: 配置対象のノード列。

    Returns:
        dict: node -> (cos(theta), sin(theta))。
    """
    positions: dict[Node, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        theta = 2 * math.pi * index / len(nodes)
        positions[node] = (math.cos(theta), math.sin(theta))
    return positions

def barycenter_angle(node: Node, free_nodes: list[Node], neighbors: dict[Node, list[Node]], fixed_positions: dict[Node, tuple[float, float]], fixed_angles: dict[Node, float]) -> float:
    """
    固定側隣接ノードの重心角度を計算する。

    Args:
        node: 自由レイヤー側の対象ノード。
        free_nodes: 自由レイヤーの現在順序。
        neighbors: node -> 固定側隣接ノード列。
        fixed_positions: 固定側ノードの単位円座標。
        fixed_angles: 固定側ノードの角度。

    Returns:
        float: ソートキーとして使う角度。
    """
    adjacent = neighbors.get(node, [])
    if not adjacent:
        return 2 * math.pi * free_nodes.index(node) / max(1, len(free_nodes))
    bx = 0.0
    by = 0.0
    for neighbor in adjacent:
        x, y = fixed_positions.get(neighbor, (0.0, 0.0))
        bx += x
        by += y
    if abs(bx) < 1e-09 and abs(by) < 1e-09:
        return fixed_angles.get(adjacent[0], 0.0)
    angle = math.atan2(by, bx)
    return angle + 2 * math.pi if angle < 0 else angle
