"""ステップ1：閉路除去"""

from dataclasses import dataclass
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


@dataclass(frozen=True)
class CycleRemovalResult:
    """レイアウト用の非巡回グラフと、反転された元の辺。"""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    reversed_edges: frozenset[Edge]


def remove_cycles(nodes: Iterable[Node], edges: Iterable[Edge]) -> CycleRemovalResult:
    """Eades--Lin--Smyth ヒューリスティックで非巡回な辺の向きを求める。

    標準的な貪欲フィードバック辺集合ヒューリスティックとして、シンク、
    ソース、最後に ``out_degree - in_degree`` が最大の頂点を繰り返し
    取り除く。得られた頂点順序に逆行する辺は、後続のレイアウト処理のために
    反転する。
    """

    node_list = tuple(dict.fromkeys(nodes))
    edge_list = tuple(dict.fromkeys(edges))
    node_set = set(node_list)
    if any(u not in node_set or v not in node_set for u, v in edge_list):
        raise ValueError("すべての辺の端点が nodes に含まれている必要があります")
    if any(u == v for u, v in edge_list):
        raise ValueError("自己ループは階層図では表現できません")

    remaining = set(node_list)
    left: list[Node] = []
    right: list[Node] = []
    node_index = {node: index for index, node in enumerate(node_list)}

    while remaining:
        indegree, outdegree = _degrees(remaining, edge_list)

        sinks = sorted(
            (v for v in remaining if outdegree[v] == 0),
            key=lambda v: node_index[v],
        )
        if sinks:
            for node in sinks:
                if node in remaining:
                    remaining.remove(node)
                    right.append(node)
            continue

        sources = sorted(
            (v for v in remaining if indegree[v] == 0),
            key=lambda v: node_index[v],
        )
        if sources:
            for node in sources:
                if node in remaining:
                    remaining.remove(node)
                    left.append(node)
            continue

        node = max(
            remaining,
            key=lambda v: (outdegree[v] - indegree[v], -node_index[v]),
        )
        remaining.remove(node)
        left.append(node)

    ordering = left + list(reversed(right))
    position = {node: index for index, node in enumerate(ordering)}
    reversed_edges = frozenset(
        (u, v) for u, v in edge_list if position[u] > position[v]
    )
    dag_edges = tuple(
        (v, u) if (u, v) in reversed_edges else (u, v) for u, v in edge_list
    )
    return CycleRemovalResult(node_list, dag_edges, reversed_edges)


def _degrees(
    remaining: set[Node], edges: tuple[Edge, ...]
) -> tuple[dict[Node, int], dict[Node, int]]:
    """各ノードの入・出次数を計算"""
    indegree = {node: 0 for node in remaining}
    outdegree = {node: 0 for node in remaining}
    for source, target in edges:
        if source in remaining and target in remaining:
            outdegree[source] += 1
            indegree[target] += 1
    return indegree, outdegree
