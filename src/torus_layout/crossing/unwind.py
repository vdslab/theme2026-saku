"""Normalize common winding using the paper's inner-segment minimum."""

from collections import defaultdict

from ..models import CrossingResult, Edge, SubdividedGraph


def unwind_levels(graph: SubdividedGraph, crossing: CrossingResult) -> CrossingResult:
    """Subtract the inner minimum from every segment of a cyclic layer pair.

    Pairs without inner segments are unchanged. Reverse edges are oriented
    consistently and duplicate occurrences share a single winding update.
    Orders and inputs remain unchanged; crossing counts are preserved.
    """
    layers = sorted(crossing.order)
    count = len(layers)
    if count < 2 or not graph.graph.edges:
        return crossing
    location = {node: index for index, layer in enumerate(layers) for node in crossing.order[layer]}
    dummy_nodes = graph.dummy_nodes
    groups: dict[int, list[tuple[Edge, int]]] = defaultdict(list)
    minimum: dict[int, int] = {}
    for edge in dict.fromkeys(graph.graph.edges):
        u, v = edge
        if u not in location or v not in location:
            raise ValueError("unwinding requires all edge endpoints in the order")
        source, target = location[u], location[v]
        if count == 2 and source != target:
            pair, direction = 0, (1 if source == 0 else -1)
        elif target == (source + 1) % count:
            pair, direction = source, 1
        elif source == (target + 1) % count:
            pair, direction = target, -1
        else:
            raise ValueError("unwinding requires cyclic adjacent-layer segments")
        groups[pair].append((edge, direction))
        if u in dummy_nodes and v in dummy_nodes:
            value = direction * crossing.winding_numbers.get(edge, 0)
            minimum[pair] = min(minimum.get(pair, value), value)
    if not any(minimum.values()):
        return crossing
    winding = dict(crossing.winding_numbers)
    for pair, value in minimum.items():
        if value:
            for edge, direction in groups[pair]:
                winding[edge] = winding.get(edge, 0) - direction * value
    return CrossingResult({layer: list(nodes) for layer, nodes in crossing.order.items()}, winding)
