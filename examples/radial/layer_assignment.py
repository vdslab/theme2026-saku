"""Assign DAG vertices to concentric radial levels."""

from collections import deque
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def assign_layers(nodes: Iterable[Node], edges: Iterable[Edge]) -> dict[Node, int]:
    """Place sinks on the outer ring and pull their predecessors inward.

    This is the radial variant of longest-path layering: all sinks share the
    outermost level, while every edge still points strictly outwards.
    """

    node_list = tuple(dict.fromkeys(nodes))
    edge_list = tuple(edges)
    successors = {node: [] for node in node_list}
    indegree = {node: 0 for node in node_list}
    for source, target in edge_list:
        if source not in successors or target not in successors:
            raise ValueError("every edge endpoint must occur in nodes")
        successors[source].append(target)
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
        raise ValueError("radial layer assignment requires an acyclic graph")

    distance_to_sink: dict[Node, int] = {}
    for node in reversed(topological_order):
        distance_to_sink[node] = max(
            (distance_to_sink[target] + 1 for target in successors[node]),
            default=0,
        )
    outermost = max(distance_to_sink.values(), default=0)
    layers: dict[Node, int] = {}
    for node in reversed(topological_order):
        layers[node] = (
            min(layers[target] for target in successors[node]) - 1
            if successors[node]
            else outermost
        )
    innermost = min(layers.values(), default=0)
    return {node: layer - innermost for node, layer in layers.items()}

