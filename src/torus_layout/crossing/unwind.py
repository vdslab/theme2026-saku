"""Subtract a common integer winding per layer pair (UNWIND-LEVEL).

Use the minimum over inner dummy-to-dummy segments when present, otherwise
the most frequent winding of the pair to minimize nonzero segment occurrences.
Adjust all segments together.
Cyclic layer pairs replace the radial paper's inner levels. This is not seam
selection; the fallback extends the paper's rule to pairs without inner edges.
"""

from collections import Counter, defaultdict

from ..models import CrossingResult, Edge, SubdividedGraph


def unwind_levels(
    graph: SubdividedGraph,
    crossing: CrossingResult,
    *,
    include_non_inner: bool = True,
) -> CrossingResult:
    """Normalize inner-segment windings without changing orders or inputs.

    Reverse edges use the opposite sign. Two layers form one pair. Duplicate
    occurrences remain in the graph, but their shared winding is updated once.
    include_non_inner=False retains just the paper's inner-segment rule.
    For each pair, winding differences (and therefore crossings) are preserved.
    Nonzero winding counts need not decrease for arbitrary input embeddings.
    """
    layers = sorted(crossing.order)
    count = len(layers)
    if count < 2 or not graph.graph.edges:
        return crossing
    location = {
        node: index
        for index, layer in enumerate(layers)
        for node in crossing.order[layer]
    }
    dummy_nodes = graph.dummy_nodes
    groups: dict[int, list[tuple[Edge, int]]] = defaultdict(list)
    minimum: dict[int, int] = {}
    frequencies: dict[int, Counter[int]] = defaultdict(Counter)
    occurrences = Counter(graph.graph.edges)
    for edge in occurrences:
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
        value = direction * crossing.winding_numbers.get(edge, 0)
        frequencies[pair][value] += occurrences[edge]
        if u in dummy_nodes and v in dummy_nodes:
            minimum[pair] = min(minimum.get(pair, value), value)
    for pair, values in frequencies.items():
        if include_non_inner and pair not in minimum:
            # Subtracting m makes precisely the segments with winding m zero.
            # Prefer no change on a tie, then the smallest absolute shift.
            minimum[pair] = min(values, key=lambda value: (-values[value], abs(value), value))
    if not any(minimum.values()):
        return crossing
    winding = dict(crossing.winding_numbers)
    for pair, value in minimum.items():
        if value:
            for edge, direction in groups[pair]:
                winding[edge] = winding.get(edge, 0) - direction * value
    return CrossingResult(
        {layer: list(nodes) for layer, nodes in crossing.order.items()}, winding
    )
