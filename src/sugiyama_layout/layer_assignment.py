"""ステップ2：非巡回グラフの頂点をレイヤーに割り当てる。"""

from collections import deque
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def assign_layers(nodes: Iterable[Node], edges: Iterable[Edge]) -> dict[Node, int]:
    """標準的な最長経路レイヤリングでランクを割り当てる。"""

    node_list = tuple(dict.fromkeys(nodes))
    edge_list = tuple(edges)
    successors = {node: [] for node in node_list}
    predecessors = {node: [] for node in node_list}
    indegree = {node: 0 for node in node_list}

    for source, target in edge_list:
        if source not in successors or target not in successors:
            raise ValueError("すべての辺の端点が nodes に含まれている必要があります")
        successors[source].append(target)
        predecessors[target].append(source)
        indegree[target] += 1

    queue = deque(node for node in node_list if indegree[node] == 0)
    topological_order: list[Node] = []
    while queue:
        node = queue.popleft()
        topological_order.append(node)
        for target in successors[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(topological_order) != len(node_list):
        raise ValueError("レイヤー割当には非巡回グラフが必要です")

    rank: dict[Node, int] = {}
    for node in topological_order:
        rank[node] = max((rank[p] + 1 for p in predecessors[node]), default=0)
    return rank
