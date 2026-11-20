"""Condense cyclic relations for Step I of Sugiyama et al. (1981)."""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass

import networkx as nx

from layout_common.cycle_removal import CycleRemovalResult


def condense_cycles(
    nodes: Iterable[Hashable], edges: Iterable[tuple[Hashable, Hashable]]
) -> CycleRemovalResult:
    """Represent each nontrivial strongly connected component by one vertex."""
    nodes = tuple(dict.fromkeys(nodes))
    edges = tuple(dict.fromkeys(edges))
    node_set = set(nodes)
    if any(source not in node_set or target not in node_set for source, target in edges):
        raise ValueError("every edge endpoint must be in nodes")

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    representative = {}
    for component in nx.strongly_connected_components(graph):
        if len(component) == 1:
            vertex = next(iter(component))
        else:
            vertex = _Component(frozenset(component))
        representative.update(dict.fromkeys(component, vertex))
    condensed_nodes = tuple(dict.fromkeys(representative[node] for node in nodes))
    condensed_edges = tuple(dict.fromkeys(
        (representative[u], representative[v])
        for u, v in edges if representative[u] != representative[v]
    ))
    return CycleRemovalResult(condensed_nodes, condensed_edges, frozenset())


@dataclass(frozen=True)
class _Component:
    members: frozenset[Hashable]

    def __str__(self):
        return "{" + ", ".join(sorted(map(str, self.members))) + "}"
