"""ステップ3：中央値スイープと隣接交換により辺の交差を削減する。

これは現代の杉山フレームワークで一般的に採用される手法である。1981年の
原論文では代わりに重心（BC）手続きが使われているため、このモジュールは
同論文をそのまま実装したものではない。
"""

from . import constants

from collections import defaultdict
from statistics import median
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def reduce_crossings(
    layers: dict[int, Iterable[Node]],
    edges: Iterable[Edge],
    sweeps: int = constants.DEFAULT_CROSSING_SWEEPS,
) -> dict[int, tuple[Node, ...]]:
    """辺の交差が少なくなるように、各レイヤー内の頂点順序を求める。

    杉山フレームワークで使われる標準的な2層間戦略として、下向きと上向きの
    中央値スイープを交互に行い、総交差数が減る場合に隣接頂点を交換する。
    """

    if sweeps < 1:
        raise ValueError("sweeps は正の値である必要があります")
    order = {layer: list(nodes) for layer, nodes in sorted(layers.items())}
    edge_list = tuple(edges)
    incoming: dict[Node, list[Node]] = defaultdict(list)
    outgoing: dict[Node, list[Node]] = defaultdict(list)
    for source, target in edge_list:
        outgoing[source].append(target)
        incoming[target].append(source)

    best = _copy_order(order)
    best_crossings = count_crossings(best, edge_list)
    layer_ids = sorted(order)

    for sweep in range(sweeps):
        downward = sweep % 2 == 0
        visited = layer_ids[1:] if downward else list(reversed(layer_ids[:-1]))
        neighbors = incoming if downward else outgoing
        reference_layer_offset = -1 if downward else 1

        for layer in visited:
            reference = order[layer + reference_layer_offset]
            reference_position = {node: index for index, node in enumerate(reference)}
            old_position = {node: index for index, node in enumerate(order[layer])}

            def key(node: Node) -> tuple[float, int]:
                positions = [
                    reference_position[neighbor]
                    for neighbor in neighbors[node]
                    if neighbor in reference_position
                ]
                return (
                    float(median(positions)) if positions else float(old_position[node]),
                    old_position[node],
                )

            order[layer].sort(key=key)
            _transpose(order, edge_list, layer)

        crossings = count_crossings(order, edge_list)
        if crossings < best_crossings:
            best = _copy_order(order)
            best_crossings = crossings

    return {layer: tuple(nodes) for layer, nodes in best.items()}


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


def _transpose(
    order: dict[int, list[Node]], edges: tuple[Edge, ...], layer: int
) -> None:
    improved = True
    while improved:
        improved = False
        index = 0
        while index + 1 < len(order[layer]):
            before = count_crossings(order, edges)
            order[layer][index], order[layer][index + 1] = (
                order[layer][index + 1],
                order[layer][index],
            )
            after = count_crossings(order, edges)
            if after < before:
                improved = True
            else:
                order[layer][index], order[layer][index + 1] = (
                    order[layer][index + 1],
                    order[layer][index],
                )
            index += 1


def _copy_order(order: dict[int, list[Node]]) -> dict[int, list[Node]]:
    return {layer: list(nodes) for layer, nodes in order.items()}
