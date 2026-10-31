"""Split long radial edges into proper adjacent-ring segments."""

from dataclasses import dataclass
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]


@dataclass(frozen=True, order=True)
class DummyNode:
    edge_index: int
    layer: int


@dataclass(frozen=True)
class ProperHierarchy:
    layers: dict[int, tuple[Node, ...]]
    edges: tuple[Edge, ...]
    dummy_nodes: frozenset[DummyNode]
    chains: dict[Edge, tuple[Node, ...]]


def insert_dummy_nodes(
    nodes: Iterable[Node],
    edges: Iterable[Edge],
    ranks: dict[Node, int],
) -> ProperHierarchy:
    """Return a proper hierarchy whose segments join consecutive rings."""

    node_list = tuple(dict.fromkeys(nodes))
    edge_list = tuple(edges)
    layers: dict[int, list[Node]] = {}
    for node in node_list:
        layers.setdefault(ranks[node], []).append(node)

    proper_edges: list[Edge] = []
    dummy_nodes: set[DummyNode] = set()
    chains: dict[Edge, tuple[Node, ...]] = {}
    for edge_index, (source, target) in enumerate(edge_list):
        source_layer = ranks[source]
        target_layer = ranks[target]
        if target_layer <= source_layer:
            raise ValueError("all layout edges must point to an outer layer")
        path: list[Node] = [source]
        for layer in range(source_layer + 1, target_layer):
            dummy = DummyNode(edge_index=edge_index, layer=layer)
            layers.setdefault(layer, []).append(dummy)
            dummy_nodes.add(dummy)
            path.append(dummy)
        path.append(target)
        chains[(source, target)] = tuple(path)
        proper_edges.extend(zip(path, path[1:]))

    layer_count = max(layers, default=-1) + 1
    return ProperHierarchy(
        layers={layer: tuple(layers.get(layer, ())) for layer in range(layer_count)},
        edges=tuple(proper_edges),
        dummy_nodes=frozenset(dummy_nodes),
        chains=chains,
    )

