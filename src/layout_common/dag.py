"""Stable DAG traversal shared by non-periodic layered layouts."""

from collections import deque
from collections.abc import Hashable, Iterable


def topological_adjacency(
    nodes: Iterable[Hashable], edges: Iterable[tuple[Hashable, Hashable]]
) -> tuple[list[Hashable], dict[Hashable, list[Hashable]], dict[Hashable, list[Hashable]]]:
    """Preserve input order and edge occurrences; reject cycles and unknown nodes."""
    node_list = tuple(dict.fromkeys(nodes))
    successors = {node: [] for node in node_list}
    predecessors = {node: [] for node in node_list}
    indegree = {node: 0 for node in node_list}
    for source, target in edges:
        if source not in successors or target not in successors:
            raise ValueError("every edge endpoint must occur in nodes")
        successors[source].append(target)
        predecessors[target].append(source)
        indegree[target] += 1
    queue = deque(node for node in node_list if indegree[node] == 0)
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for target in successors[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(node_list):
        raise ValueError("layer assignment requires an acyclic graph")
    return order, successors, predecessors
