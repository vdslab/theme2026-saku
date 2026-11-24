"""Exact cyclic seam selection with range-add/min dynamic programming.

Count subdivided segments with nonzero winding, not original edges or the
number of times a segment wraps. Cyclic node orders and integer-turn choices
are fixed; each gap is represented by a left rotation in [0, layer size).
"""

from dataclasses import dataclass

from ..models import CrossingResult, Layers, Node, SubdividedGraph

_INFINITY = 10**30


class _RangeMinimum:
    """Lazy range addition with a deterministic leftmost argmin."""

    def __init__(self, values: list[int]) -> None:
        size = 1
        while size < len(values):
            size *= 2
        self.size = size
        self.minimum = [_INFINITY] * (2 * size)
        self.lazy = [0] * (2 * size)
        self.argmin = [0] * (2 * size)
        for index in range(size):
            self.argmin[size + index] = index
        self.minimum[size : size + len(values)] = values
        for index in range(size - 1, 0, -1):
            self._pull(index)

    def _pull(self, index: int) -> None:
        left, right = 2 * index, 2 * index + 1
        child = left if self.minimum[left] <= self.minimum[right] else right
        self.minimum[index] = self.minimum[child] + self.lazy[index]
        self.argmin[index] = self.argmin[child]

    def add(self, start: int, stop: int, delta: int) -> None:
        if start < stop and delta:
            self._add(1, 0, self.size, start, stop, delta)

    def _add(
        self, index: int, left: int, right: int, start: int, stop: int, delta: int
    ) -> None:
        if start <= left and right <= stop:
            self.minimum[index] += delta
            self.lazy[index] += delta
            return
        middle = (left + right) // 2
        if start < middle:
            self._add(2 * index, left, middle, start, stop, delta)
        if stop > middle:
            self._add(2 * index + 1, middle, right, start, stop, delta)
        self._pull(index)


@dataclass(frozen=True)
class _Pair:
    source_size: int
    target_size: int
    # Source position, target position, oriented winding, and crossing cost.
    segments: tuple[tuple[int, int, int, int], ...]
    initial: tuple[int, ...]
    events: tuple[tuple[tuple[int, int, int], ...], ...]


def _prepare_pair(
    source_size: int, target_size: int, segments: list[tuple[int, int, int, int]]
) -> _Pair:
    # C(a, 0): baseline plus one suffix adjustment per segment.
    baseline = sum(weight for _, _, winding, weight in segments if winding != 0)
    difference = [0] * (source_size + 1)
    events: list[list[tuple[int, int, int]]] = [[] for _ in range(target_size)]
    for source, target, winding, weight in segments:
        difference[source + 1] += weight * (int(winding + 1 != 0) - int(winding != 0))
        prefix = weight * (int(winding - 1 != 0) - int(winding != 0))
        suffix = weight * (int(winding != 0) - int(winding + 1 != 0))
        if prefix or suffix:
            events[target].append((source + 1, prefix, suffix))
    initial: list[int] = []
    value = baseline
    for delta in difference[:-1]:
        value += delta
        initial.append(value)
    return _Pair(
        source_size, target_size, tuple(segments), tuple(initial),
        tuple(tuple(group) for group in events),
    )


def _transition(values: list[int], pair: _Pair) -> tuple[list[int], list[int]]:
    tree = _RangeMinimum([value + cost for value, cost in zip(values, pair.initial)])
    result = [tree.minimum[1]]
    parents = [tree.argmin[1]]
    for boundary in range(pair.target_size - 1):
        for split, prefix, suffix in pair.events[boundary]:
            tree.add(0, split, prefix)
            tree.add(split, pair.source_size, suffix)
        result.append(tree.minimum[1])
        parents.append(tree.argmin[1])
    return result, parents


def _closing_costs(pair: _Pair, target_gap: int) -> list[int]:
    """C(a, target_gap) in linear time without materializing a matrix."""
    difference = [0] * (pair.source_size + 1)
    baseline = 0
    for source, target, winding, weight in pair.segments:
        adjusted = winding - int(target < target_gap)
        baseline += weight * int(adjusted != 0)
        difference[source + 1] += weight * (int(adjusted + 1 != 0) - int(adjusted != 0))
    result: list[int] = []
    value = baseline
    for delta in difference[:-1]:
        value += delta
        result.append(value)
    return result


def count_seam_segments(graph: SubdividedGraph, crossing: CrossingResult) -> int:
    """Count each subdivided edge occurrence once if its winding is nonzero."""
    return sum(crossing.winding_numbers.get(edge, 0) != 0 for edge in graph.graph.edges)


def seam_score(
    graph: SubdividedGraph, crossing: CrossingResult, prioritize_internal: bool,
) -> tuple[int, int]:
    """Compare internal seam segments first when requested, then all segments."""
    dummy = graph.dummy_nodes if prioritize_internal else set()
    total = internal = 0
    for u, v in graph.graph.edges:
        if crossing.winding_numbers.get((u, v), 0) != 0:
            total += 1
            internal += u in dummy and v in dummy
    return internal, total


def _pairs(
    graph: SubdividedGraph, crossing: CrossingResult, layers: list[int], internal_penalty: int,
) -> list[_Pair]:
    location: dict[Node, tuple[int, int]] = {
        node: (index, position)
        for index, layer in enumerate(layers)
        for position, node in enumerate(crossing.order[layer])
    }
    groups: list[list[tuple[int, int, int, int]]] = [[] for _ in layers]
    dummy = graph.dummy_nodes if internal_penalty else set()
    count = len(layers)
    for edge in graph.graph.edges:
        u, v = edge
        source, p = location[u]
        target, q = location[v]
        winding = crossing.winding_numbers.get(edge, 0)
        weight = 1 + (internal_penalty if u in dummy and v in dummy else 0)
        # For two layers both directions belong to one pair, never both.
        if count == 2 and source != target:
            if source == 0:
                groups[0].append((p, q, winding, weight))
            else:
                groups[0].append((q, p, -winding, weight))
        elif target == (source + 1) % count:
            groups[source].append((p, q, winding, weight))
        elif source == (target + 1) % count:
            groups[target].append((q, p, -winding, weight))
        else:
            raise ValueError("seam optimization requires edges between cyclic adjacent layers")
    sizes = [max(1, len(crossing.order[layer])) for layer in layers]
    return [
        _prepare_pair(sizes[index], sizes[(index + 1) % count], segments)
        for index, segments in enumerate(groups)
    ]


def optimize_seam(
    graph: SubdividedGraph, crossing: CrossingResult, *, prioritize_internal: bool = False,
) -> CrossingResult:
    """Minimize seam segments over all gap combinations without mutating inputs.

    Proper cyclic adjacent-layer edges are required for two or more layers.
    Empty layers have one inert candidate; zero/one-layer inputs are unchanged.
    When requested, internal segment count takes precedence over total count.
    Each candidate is a left rotation of the supplied order by less than one
    turn. Applying the optimizer again to its result can compose a full turn.
    The original embedding is retained on a tie in cost. No dense
    cost matrices or three-dimensional DP table are allocated.
    """
    layers = sorted(crossing.order)
    if len(layers) < 2 or not graph.graph.edges:
        return crossing
    # A small start layer reduces the number of independent cyclic DP passes.
    start = min(range(len(layers)), key=lambda i: max(1, len(crossing.order[layers[i]])))
    layers = layers[start:] + layers[:start]
    # A single internal crossing costs more than every possible change in the
    # total count, so the scalar DP has the same ordering as the two counts.
    internal_penalty = len(graph.graph.edges) + 1 if prioritize_internal else 0
    pairs = _pairs(graph, crossing, layers, internal_penalty)
    internal, total = seam_score(graph, crossing, prioritize_internal)
    best_cost = internal_penalty * internal + total
    best_gaps: list[int] | None = None
    for start_gap in range(pairs[0].source_size):
        values = [_INFINITY] * pairs[0].source_size
        values[start_gap] = 0
        parents: list[list[int]] = []
        for pair in pairs[:-1]:
            values, previous = _transition(values, pair)
            parents.append(previous)
        closing = _closing_costs(pairs[-1], start_gap)
        end = min(range(len(values)), key=lambda gap: (values[gap] + closing[gap], gap))
        cost = values[end] + closing[end]
        if cost >= best_cost:
            continue
        best_cost = cost
        gaps = [end]
        for previous in reversed(parents):
            end = previous[end]
            gaps.append(end)
        best_gaps = list(reversed(gaps))
    if best_gaps is None:
        return crossing
    shifts = {
        node: int(position < gap)
        for layer, gap in zip(layers, best_gaps)
        for position, node in enumerate(crossing.order[layer])
    }
    order: Layers = {layer: list(nodes) for layer, nodes in crossing.order.items()}
    for layer, gap in zip(layers, best_gaps):
        nodes = crossing.order[layer]
        order[layer] = nodes[gap:] + nodes[:gap]
    winding = dict(crossing.winding_numbers)
    for edge in graph.graph.edges:
        u, v = edge
        winding[edge] = crossing.winding_numbers.get(edge, 0) + shifts[u] - shifts[v]
    return CrossingResult(order, winding)
