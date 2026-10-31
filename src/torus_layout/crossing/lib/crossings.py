"""2層・全体の交差数と局所差分。"""
import math
from collections import defaultdict
from ...models import Node, Edge, Layers, Winding
from .types import OrientedEdge, EdgeLike
from .embedding import edge_endpoints

def pair_positions(order: Layers, fixed_layer: int, free_layer: int) -> tuple[dict[Node, int], dict[Node, int]]:
    """2層間の交差差分計算に使う頂点位置を返す。"""
    return ({node: index for index, node in enumerate(order[fixed_layer])}, {node: index for index, node in enumerate(order[free_layer])})

def crossings_for_edge[E: EdgeLike](edge: E, pair_edges: list[E], order: Layers, psi: dict[E, int], fixed_layer: int, free_layer: int, edge_weights: dict[E, int] | None=None) -> int:
    """指定辺と他の全辺の交差数を返す。"""
    pi_fixed, pi_free = pair_positions(order, fixed_layer, free_layer)
    return sum((weighted_edge_crossings(edge, other, pi_fixed, pi_free, psi, edge_weights) for other in pair_edges if other != edge))

def crossings_between_edge_sets[E: EdgeLike](first_edges: list[E], second_edges: list[E], order: Layers, psi: dict[E, int], fixed_layer: int, free_layer: int, edge_weights: dict[E, int] | None=None) -> int:
    """2つの辺集合の間で生じる交差数を返す。"""
    pi_fixed, pi_free = pair_positions(order, fixed_layer, free_layer)
    return sum((weighted_edge_crossings(edge1, edge2, pi_fixed, pi_free, psi, edge_weights) for edge1 in first_edges for edge2 in second_edges))

def crossings_involving_edges[E: EdgeLike](incident_edges: list[E], pair_edges: list[E], order: Layers, psi: dict[E, int], fixed_layer: int, free_layer: int, edge_weights: dict[E, int] | None=None) -> int:
    """incident_edgesのいずれかを含む辺対の交差数を1回ずつ数える。"""
    pi_fixed, pi_free = pair_positions(order, fixed_layer, free_layer)
    incident_set = set(incident_edges)
    other_edges = [edge for edge in pair_edges if edge not in incident_set]
    crossings = sum((weighted_edge_crossings(edge1, edge2, pi_fixed, pi_free, psi, edge_weights) for edge1 in incident_edges for edge2 in other_edges))
    for index, edge1 in enumerate(incident_edges):
        for edge2 in incident_edges[index + 1:]:
            crossings += weighted_edge_crossings(edge1, edge2, pi_fixed, pi_free, psi, edge_weights)
    return crossings

def sifting_edge_weights(pair_edges: list[OrientedEdge], dummy_nodes: set[Node] | None, edge_count: int) -> dict[OrientedEdge, int]:
    """inner segmentの交差重みを論文どおり|E|にする。"""
    dummy_nodes = set() if dummy_nodes is None else set(dummy_nodes)
    inner_weight = max(1, edge_count)
    return {edge: inner_weight if edge[0] in dummy_nodes and edge[1] in dummy_nodes else 1 for edge in pair_edges}

def weighted_edge_crossings[E: EdgeLike](edge1: E, edge2: E, pi_fixed: dict[Node, int], pi_free: dict[Node, int], psi: dict[E, int], edge_weights: dict[E, int] | None=None) -> int:
    """inner segmentが関わる交差だけ重み付きで返す。"""
    crossings = crossings_between_edges(edge1, edge2, pi_fixed, pi_free, psi)
    if edge_weights is None:
        return crossings
    return crossings * max(edge_weights.get(edge1, 1), edge_weights.get(edge2, 1))

def pair_crossings[E: EdgeLike](order: Layers, psi: dict[E, int], fixed_layer: int, free_layer: int, pair_edges: list[E], edge_weights: dict[E, int] | None=None) -> int:
    """処理中の2層ペアの交差数だけを返す。"""
    return count_layer_pair_crossings(order, psi, fixed_layer, free_layer, pair_edges, edge_weights=edge_weights)

def count_all_crossings[E: EdgeLike](order: Layers, psi: dict[E, int], layers: list[int], edges: list[E]) -> int:
    """
    全ての隣接レイヤーペアの交差数を合計する。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        layers: レイヤーキー列。
        edges: エッジ集合。

    Returns:
        int: 総交差数。
    """
    total = 0
    for index, fixed_layer in enumerate(layers):
        free_layer = layers[(index + 1) % len(layers)]
        total += count_layer_pair_crossings(order, psi, fixed_layer, free_layer, edges)
    return total

def count_layer_pair_crossings[E: EdgeLike](order: Layers, psi: dict[E, int], fixed_key: int, free_key: int, edges: list[E], edge_weights: dict[E, int] | None=None) -> int:
    """
    1つの隣接レイヤーペア間の交差数を数える。

    Args:
        order: 各レイヤー内のノード順序。
        psi: 各エッジの上下境界巻き数。
        fixed_key: 左側レイヤーキー。
        free_key: 右側レイヤーキー。
        edges: エッジ集合。

    Returns:
        int: このレイヤーペア内の交差数。
    """
    fixed_nodes = order[fixed_key]
    free_nodes = order[free_key]
    pi_fixed = {node: index for index, node in enumerate(fixed_nodes)}
    pi_free = {node: index for index, node in enumerate(free_nodes)}
    edges_between = edges_between_layers(order, fixed_key, free_key, edges)
    crossings = 0
    for i, edge1 in enumerate(edges_between):
        for edge2 in edges_between[i + 1:]:
            crossings += weighted_edge_crossings(edge1, edge2, pi_fixed, pi_free, psi, edge_weights)
    return crossings

def edges_between_layers[E: EdgeLike](order: Layers, fixed_key: int, free_key: int, edges: list[E]) -> list[E]:
    """fixed_keyからfree_keyへ向かう辺だけを抽出する。"""
    fixed_nodes = set(order[fixed_key])
    free_nodes = set(order[free_key])
    return [edge for edge in edges if edge_endpoints(edge)[0] in fixed_nodes and edge_endpoints(edge)[1] in free_nodes]

def crossings_between_edges[E: EdgeLike](edge1: E, edge2: E, pi_fixed: dict[Node, int], pi_free: dict[Node, int], psi: dict[E, int]) -> int:
    """
    2本の隣接レイヤー間エッジが交差する数を計算する。

    Args:
        edge1: 1本目のエッジ。
        edge2: 2本目のエッジ。
        pi_fixed: 左側レイヤーの node -> index。
        pi_free: 右側レイヤーの node -> index。
        psi: 各エッジの上下境界巻き数。

    Returns:
        int: 交差数。
    """
    fixed1, free1 = edge_endpoints(edge1)
    fixed2, free2 = edge_endpoints(edge2)
    _sign = lambda value: 1 if value > 0 else -1 if value < 0 else 0
    a = _sign(pi_fixed[fixed2] - pi_fixed[fixed1])
    b = _sign(pi_free[free2] - pi_free[free1])
    delta = psi.get(edge2, 0) - psi.get(edge1, 0)
    value = abs(delta + (b - a) / 2) - 1 + (abs(a) + abs(b)) / 2
    return max(0, int(round(value)))
