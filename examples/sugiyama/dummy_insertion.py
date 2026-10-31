"""複数レイヤーにまたがる辺を分割し、階層を正規化する。"""

from dataclasses import dataclass
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


@dataclass(frozen=True, order=True)
class DummyNode:
    """長い辺に挿入する折れ曲がり点。"""

    edge_index: int
    layer: int


@dataclass(frozen=True)
class ProperHierarchy:
    """すべての辺が隣接レイヤー間を結ぶグラフ。"""

    layers: dict[int, tuple[Node, ...]]
    edges: tuple[Edge, ...]
    dummy_nodes: frozenset[DummyNode]
    chains: dict[Edge, tuple[Node, ...]]


def insert_dummy_nodes(
    nodes: Iterable[Node],
    edges: Iterable[Edge],
    ranks: dict[Node, int],
) -> ProperHierarchy:
    """各長辺を、ダミー頂点を経由する辺の連鎖に置き換える。"""

    node_list = tuple(dict.fromkeys(nodes))
    edge_list = tuple(edges)
    layers: dict[int, list[Node]] = {}
    for node in node_list:
        layers.setdefault(ranks[node], []).append(node)

    proper_edges: list[Edge] = []
    dummy_nodes: set[DummyNode] = set()
    chains: dict[Edge, tuple[Node, ...]] = {}

    for edge_index, (source, target) in enumerate(edge_list):
        source_rank = ranks[source]
        target_rank = ranks[target]
        if target_rank <= source_rank:
            raise ValueError("すべてのレイアウト辺が後続レイヤーを向く必要があります")

        path: list[Node] = [source]
        for layer in range(source_rank + 1, target_rank):
            dummy = DummyNode(edge_index=edge_index, layer=layer)
            dummy_nodes.add(dummy)
            layers.setdefault(layer, []).append(dummy)
            path.append(dummy)
        path.append(target)
        chains[(source, target)] = tuple(path)
        proper_edges.extend(zip(path, path[1:]))

    ordered_layers = {
        layer: tuple(layers.get(layer, ()))
        for layer in range(max(layers, default=-1) + 1)
    }
    return ProperHierarchy(
        layers=ordered_layers,
        edges=tuple(proper_edges),
        dummy_nodes=frozenset(dummy_nodes),
        chains=chains,
    )
