"""ステップ2：非巡回グラフの頂点をレイヤーに割り当てる。"""

from typing import Hashable, Iterable, TypeAlias

from layout_common.dag import topological_adjacency

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def assign_layers(nodes: Iterable[Node], edges: Iterable[Edge]) -> dict[Node, int]:
    """標準的な最長経路レイヤリングでランクを割り当てる。"""

    topological_order, _, predecessors = topological_adjacency(nodes, edges)

    rank: dict[Node, int] = {}
    for node in topological_order:
        rank[node] = max((rank[p] + 1 for p in predecessors[node]), default=0)
    return rank
