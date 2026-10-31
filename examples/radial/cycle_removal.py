"""Make a directed graph acyclic before radial layer assignment."""

from dataclasses import dataclass
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


@dataclass(frozen=True)
class CycleRemovalResult:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    reversed_edges: frozenset[Edge]


def remove_cycles(nodes: Iterable[Node], edges: Iterable[Edge]) -> CycleRemovalResult:
    """Reverse feedback edges found by a deterministic greedy heuristic."""

    node_list = tuple(dict.fromkeys(nodes))
    edge_list = tuple(dict.fromkeys(edges))
    node_set = set(node_list)
    if any(source not in node_set or target not in node_set for source, target in edge_list):
        raise ValueError("every edge endpoint must occur in nodes")
    if any(source == target for source, target in edge_list):
        raise ValueError("self-loops cannot be represented by a layered drawing")

    remaining = set(node_list)
    left: list[Node] = []
    right: list[Node] = []
    node_index = {node: index for index, node in enumerate(node_list)}

    while remaining:
        indegree = {node: 0 for node in remaining}
        outdegree = {node: 0 for node in remaining}
        for source, target in edge_list:
            if source in remaining and target in remaining:
                outdegree[source] += 1
                indegree[target] += 1

        sinks = sorted(
            (node for node in remaining if outdegree[node] == 0),
            key=node_index.__getitem__,
        )
        if sinks:
            for node in sinks:
                remaining.remove(node)
                right.append(node)
            continue

        sources = sorted(
            (node for node in remaining if indegree[node] == 0),
            key=node_index.__getitem__,
        )
        if sources:
            for node in sources:
                remaining.remove(node)
                left.append(node)
            continue

        node = max(
            remaining,
            key=lambda candidate: (
                outdegree[candidate] - indegree[candidate],
                -node_index[candidate],
            ),
        )
        remaining.remove(node)
        left.append(node)

    ordering = left + list(reversed(right))
    position = {node: index for index, node in enumerate(ordering)}
    reversed_edges = frozenset(
        edge for edge in edge_list if position[edge[0]] > position[edge[1]]
    )
    dag_edges = tuple(
        (target, source) if (source, target) in reversed_edges else (source, target)
        for source, target in edge_list
    )
    return CycleRemovalResult(node_list, dag_edges, reversed_edges)

