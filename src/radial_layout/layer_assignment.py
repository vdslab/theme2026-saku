"""Assign DAG vertices to concentric radial levels."""

from typing import Hashable, Iterable, TypeAlias

from layout_common.dag import topological_adjacency

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


def assign_layers(nodes: Iterable[Node], edges: Iterable[Edge]) -> dict[Node, int]:
    """Place sinks on the outer ring and pull their predecessors inward.

    This is the radial variant of longest-path layering: all sinks share the
    outermost level, while every edge still points strictly outwards.
    """

    topological_order, successors, _ = topological_adjacency(nodes, edges)

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

