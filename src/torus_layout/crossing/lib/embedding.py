"""巻き数と回転の計算。"""
import math
from collections import defaultdict
from ...models import Node, Edge, Layers, Winding
from .types import OrientedEdge, EdgeLike
OFFSET_VALUES = (-1,0,1)

def base_order(layer_dict: Layers, layers: list[int]) -> Layers:
    """
    レイヤー辞書から探索用の順序辞書を作る。

    Args:
        layer_dict: レイヤーごとのノードリスト。
        layers: 使用するレイヤーキー列。

    Returns:
        dict: 各レイヤーのノード順序のコピー。
    """
    return {layer: list(layer_dict[layer]) for layer in layers}

def copy_order(order: Layers) -> Layers:
    """
    orderをレイヤー単位で浅くコピーする。

    Args:
        order: 各レイヤー内のノード順序。

    Returns:
        dict: ノードリストを複製したorder。
    """
    return {layer: list(nodes) for layer, nodes in order.items()}

def map_node_layers(order: Layers) -> dict[Node, int]:
    """
    ノードから所属レイヤーを引ける辞書を作る。

    Args:
        order: 各レイヤー内のノード順序。

    Returns:
        dict: node -> layer。
    """
    node_to_layer: dict[Node, int] = {}
    for layer, nodes in order.items():
        for node in nodes:
            node_to_layer[node] = layer
    return node_to_layer

def edge_endpoints(edge: EdgeLike) -> Edge:
    """通常辺と2層処理用の一時ID付き辺から端点を返す。"""
    return (edge[0], edge[1])

def forward_layer_pairs(layers: list[int]) -> list[tuple[int, int]]:
    """順方向1 sweepの循環隣接レイヤーペアを返す。"""
    if len(layers) < 2:
        return []
    return [(layer, layers[(index + 1) % len(layers)]) for index, layer in enumerate(layers)]

def oriented_pair_embedding(order: Layers, psi: Winding, fixed_layer: int, free_layer: int, edges: list[Edge]) -> tuple[list[OrientedEdge], dict[OrientedEdge, int], dict[OrientedEdge, tuple[Edge, int]]]:
    """2層間の辺をfixed→freeへ揃え、向きに合わせてpsiを変換する。"""
    fixed_nodes = set(order[fixed_layer])
    free_nodes = set(order[free_layer])
    pair_edges: list[OrientedEdge] = []
    oriented_psi: dict[OrientedEdge, int] = {}
    original_edges: dict[OrientedEdge, tuple[Edge, int]] = {}
    for edge_index, edge in enumerate(edges):
        u, v = edge_endpoints(edge)
        if u in fixed_nodes and v in free_nodes:
            '順方向にswapする時に利用'
            oriented_edge = (u, v, edge_index)
            direction = 1
        elif u in free_nodes and v in fixed_nodes:
            '逆方向にswapする時に利用'
            oriented_edge = (v, u, edge_index)
            direction = -1
        else:
            continue
        pair_edges.append(oriented_edge)
        oriented_psi[oriented_edge] = direction * psi.get(edge, 0)
        original_edges[oriented_edge] = (edge, direction)
    return (pair_edges, oriented_psi, original_edges)

def postprocess_sifting_rotations(order: Layers, psi: Winding, layers: list[int], edges: list[Edge]) -> None:
    """Algorithm 2を各循環隣接レイヤーペアに1回ずつ適用する。"""
    for fixed_layer, free_layer in forward_layer_pairs(layers):
        postprocess_two_layer_rotation(fixed_layer, free_layer, order, psi, edges)

def postprocess_two_layer_rotation(fixed_layer: int, free_layer: int, order: Layers, psi: Winding, edges: list[Edge]) -> None:
    """辺の平均角度差に基づき、自由層を一括回転する。"""
    fixed_nodes = order[fixed_layer]
    free_nodes = order[free_layer]
    if not fixed_nodes or len(free_nodes) <= 1:
        return
    pair_edges, oriented_psi, _ = oriented_pair_embedding(order, psi, fixed_layer, free_layer, edges)
    if not pair_edges:
        return
    fixed_positions = {node: index for index, node in enumerate(fixed_nodes)}
    free_positions = {node: index for index, node in enumerate(free_nodes)}
    fixed_step = 2 * math.pi / len(fixed_nodes)
    free_step = 2 * math.pi / len(free_nodes)
    average_span = sum((free_positions[edge[1]] * free_step - fixed_positions[edge[0]] * fixed_step + 2 * math.pi * oriented_psi[edge] for edge in pair_edges)) / len(pair_edges)
    rotation_steps = math.floor(average_span / free_step + 0.5)
    rotate_layer_preserving_embedding(free_layer, rotation_steps, order, psi, edges)

def rotate_layer_preserving_embedding(layer: int, steps: int, order: Layers, psi: Winding, edges: list[Edge]) -> None:
    """レイヤーを左回転し、同じradial embeddingを表すようpsiを更新する。"""
    nodes = order[layer]
    if len(nodes) <= 1 or steps == 0:
        return
    node_to_layer = map_node_layers(order)
    cut_crossings = rotation_cut_crossings(nodes, steps)
    for edge in edges:
        u, v = edge_endpoints(edge)
        source_crossings = cut_crossings.get(u, 0) if node_to_layer.get(u) == layer else 0
        target_crossings = cut_crossings.get(v, 0) if node_to_layer.get(v) == layer else 0
        delta = source_crossings - target_crossings
        if delta:
            psi[edge] = psi.get(edge, 0) + delta
    shift = steps % len(nodes)
    order[layer] = list(nodes[shift:]) + list(nodes[:shift])

def rotation_cut_crossings(nodes: list[Node], steps: int) -> dict[Node, int]:
    """循環回転で各頂点が基準rayを跨ぐ符号付き回数を返す。"""
    size = len(nodes)
    counts: dict[Node, int] = {}
    if steps > 0:
        full_turns, remainder = divmod(steps, size)
        for index, node in enumerate(nodes):
            counts[node] = full_turns + (1 if index < remainder else 0)
    else:
        full_turns, remainder = divmod(-steps, size)
        boundary = size - remainder
        for index, node in enumerate(nodes):
            counts[node] = -full_turns - (1 if remainder and index >= boundary else 0)
    return counts

def compute_winding_numbers(A: list[Edge], order: Layers, L: Layers, layers: list[int]) -> Winding:
    """
    現在のorderに対する各エッジの初期psiを計算する。

    Args:
        A: エッジ集合。
        order: 各レイヤー内のノード順序。
        L: レイヤー辞書。
        layers: レイヤーキー列。
    Returns:
        dict: edge -> psi。
    """
    psi: Winding = {}
    node_to_layer = map_node_layers(L)
    layer_index = {layer: index for index, layer in enumerate(layers)}
    for edge in A:
        psi[edge] = best_winding_for_edge(edge, order, node_to_layer, layer_index, layers)
    return psi

def best_winding_for_edge(edge: Edge, order: Layers, node_to_layer: dict[Node, int], layer_index: dict[int, int], layers: list[int]) -> int:
    """
    1本のエッジについて幾何的に最短となるpsiを選ぶ。

    Args:
        edge: 対象エッジ。
        order: 各レイヤー内のノード順序。
        node_to_layer: node -> layer。
        layer_index: layer -> index。
        layers: レイヤーキー列。

    Returns:
        int: -1, 0, 1 のいずれかのpsi。
    """
    u, v = edge
    u_layer = node_to_layer.get(u)
    v_layer = node_to_layer.get(v)
    if u_layer is None or v_layer is None or u_layer == v_layer:
        return 0
    if (layer_index[v_layer] - layer_index[u_layer]) % len(layers) != 1:
        return 0
    u_nodes = order.get(u_layer, [])
    v_nodes = order.get(v_layer, [])
    if u not in u_nodes or v not in v_nodes or (not u_nodes) or (not v_nodes):
        return 0
    theta_u = 2 * math.pi * u_nodes.index(u) / len(u_nodes)
    theta_v = 2 * math.pi * v_nodes.index(v) / len(v_nodes)
    delta_theta = theta_v - theta_u
    return min(OFFSET_VALUES, key=lambda offset: abs(delta_theta + 2 * math.pi * offset))
