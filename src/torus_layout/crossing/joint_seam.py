"""Joint seam and common-turn optimization on cyclic adjacent layer pairs."""

from collections import Counter
from math import inf
from typing import NamedTuple

from ..models import CrossingResult, Edge, Layers, SubdividedGraph
from .seam import seam_score


type _Cost = int | float


class _Segment(NamedTuple):
    source: int
    target: int
    winding: int
    internal: bool
    edge: Edge
    direction: int


def _pair_costs(
    graph: SubdividedGraph, crossing: CrossingResult, layers: list[int],
) -> tuple[list[int], list[list[_Segment]], list[list[list[_Cost]]]]:
    sizes = [max(1, len(crossing.order[layer])) for layer in layers]
    location = {u: (i, rank) for i, layer in enumerate(layers)
                for rank, u in enumerate(crossing.order[layer])}
    strips: list[list[_Segment]] = [[] for _ in layers]
    dummy = graph.dummy_nodes
    for edge in graph.graph.edges:
        u, v = edge
        i, p = location[u]
        j, q = location[v]
        if i == j or (j - i) % len(layers) not in (1, len(layers) - 1):
            raise ValueError("joint optimization requires cyclic adjacent-layer segments")
        winding = crossing.winding_numbers.get(edge, 0)
        direction = 1
        if j != (i + 1) % len(layers) or (len(layers) == 2 and i == 1):
            i, p, q, winding, direction = j, q, p, -winding, -1
        strips[i].append(_Segment(p, q, winding, u in dummy and v in dummy, edge, direction))

    tables = [
        _strip_costs(strip, sizes[i], sizes[(i + 1) % len(layers)])
        for i, strip in enumerate(strips)
    ]
    return sizes, strips, tables


def _adjust_frequency(
    counts: Counter[int], frequency_sizes: Counter[int], value: int, delta: int, maximum: int,
) -> int:
    """Update the mode frequency when a single count changes by one."""
    old = counts[value]
    new = old + delta
    if old:
        frequency_sizes[old] -= 1
    if new:
        frequency_sizes[new] += 1
        counts[value] = new
    else:
        del counts[value]
    maximum = max(maximum, new)
    return maximum if maximum == 0 or frequency_sizes[maximum] else maximum - 1


def _strip_costs(
    strip: list[_Segment], source_size: int, target_size: int,
) -> list[list[_Cost]]:
    # Sweep the target cut. Only segments ending at the crossed rank change.
    events = [[] for _ in range(target_size)]
    for p, q, winding, internal, _, _ in strip:
        events[q].append((p, winding, internal))

    table = []
    for a in range(source_size):
        counts = Counter()
        internal_counts = Counter()
        for p, _, winding, internal, _, _ in strip:
            value = winding + (p < a)
            counts[value] += 1
            if internal:
                internal_counts[value] += 1
        frequency_sizes = Counter(counts.values())
        maximum = max(counts.values(), default=0)
        row = []
        for b, group in enumerate(events):
            if not internal_counts:
                row.append(len(strip) - maximum)
            elif len(internal_counts) == 1:
                row.append(len(strip) - counts[next(iter(internal_counts))])
            else:
                row.append(inf)

            if b + 1 == target_size:
                break
            for p, winding, internal in group:
                value = winding + (p < a)
                maximum = _adjust_frequency(counts, frequency_sizes, value, -1, maximum)
                maximum = _adjust_frequency(counts, frequency_sizes, value - 1, 1, maximum)
                if internal:
                    internal_counts[value] -= 1
                    if not internal_counts[value]:
                        del internal_counts[value]
                    internal_counts[value - 1] += 1
        table.append(row)
    return table


def optimize_joint_seam(graph: SubdividedGraph, crossing: CrossingResult) -> CrossingResult | None:
    """Minimize all seam segments while requiring zero dummy-to-dummy seams.

    Each adjacent layer pair may apply an independent common integer turn.
    Return None when no combination satisfies the internal-segment constraint.
    Cyclic node orders and crossings are preserved.
    """
    if not graph.graph.edges:
        return crossing
    layers = sorted(crossing.order)
    if len(layers) < 2:
        return crossing if seam_score(graph, crossing, True)[0] == 0 else None
    start_layer = min(range(len(layers)), key=lambda i: max(1, len(crossing.order[layers[i]])))
    layers = layers[start_layer:] + layers[:start_layer]
    sizes, strips, tables = _pair_costs(graph, crossing, layers)
    best = inf
    best_gaps: list[int] | None = None
    for start in range(sizes[0]):
        values = list(tables[0][start])
        parents = []
        for table, size in zip(tables[1:-1], sizes[2:]):
            next_values, previous = [inf] * size, [0] * size
            for a, (value, row) in enumerate(zip(values, table)):
                if value == inf:
                    continue
                for b, cost in enumerate(row):
                    candidate = value + cost
                    if candidate < next_values[b]:
                        next_values[b] = candidate
                        previous[b] = a
            values = next_values
            parents.append(previous)
        for end, value in enumerate(values):
            score = value + tables[-1][end][start]
            if score < best:
                best = score
                gaps = [end]
                for previous in reversed(parents):
                    gaps.append(previous[gaps[-1]])
                best_gaps = [start, *reversed(gaps)]
    if best_gaps is None:
        return None
    order: Layers = {}
    winding = dict(crossing.winding_numbers)
    for i, (layer, a) in enumerate(zip(layers, best_gaps)):
        nodes = crossing.order[layer]
        order[layer] = nodes[a:] + nodes[:a]
        b = best_gaps[(i + 1) % len(layers)]
        adjusted = [
            (value + (p < a) - (q < b), internal, edge, direction)
            for p, q, value, internal, edge, direction in strips[i]
        ]
        counts = Counter(value for value, _, _, _ in adjusted)
        required = next((value for value, internal, _, _ in adjusted if internal), None)
        if required is None:
            required = min(counts, key=lambda value: (-counts[value], abs(value), value), default=0)
        for value, _, edge, direction in adjusted:
            winding[edge] = direction * (value - required)
    return CrossingResult(order, winding)
