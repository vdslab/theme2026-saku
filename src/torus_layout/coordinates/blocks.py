"""Place dummy paths as shared vertical coordinates under fixed layer orders."""

from collections import defaultdict
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from ..domain import vertical_bounds
from ..models import Layers, Node, Positions, SubdividedGraph, Winding
from ..subdivision import build_dummy_blocks


@dataclass
class BlockConstraints:
    order: tuple[Node, ...]
    predecessors: dict[Node, set[Node]]
    lower: dict[Node, int]
    latest: dict[Node, int]
    period: int


class UnsplitBlockOrderError(ValueError):
    """The layer orders cannot be realized with a single y per dummy block."""


def _block_constraints(
    order: Layers, block_of: dict[Node, Node], period: int | None,
) -> BlockConstraints | None:
    # Work in units of min_gap, with the same rank bounds as the BK projection.
    predecessors: dict[Node, set[Node]] = defaultdict(set)
    successors: dict[Node, set[Node]] = defaultdict(set)
    lower: dict[Node, int] = {}
    trailing: dict[Node, int] = {}
    for nodes in order.values():
        blocks = [block_of[node] for node in nodes]
        for rank, block in enumerate(blocks):
            lower[block] = max(lower.get(block, 0), rank)
            trailing[block] = max(trailing.get(block, 0), len(nodes) - rank)
            if rank:
                predecessors[block].add(blocks[rank - 1])
                successors[blocks[rank - 1]].add(block)

    sorter = TopologicalSorter(dict.fromkeys(lower, ()))
    for block in lower:
        sorter.add(block, *predecessors[block])
    try:
        sequence = tuple(sorter.static_order())
    except CycleError:
        return None
    if period is None:
        # The earliest feasible height at each block forces that height plus
        # its trailing rank allowance into the shared period.
        earliest = lower.copy()
        for block in sequence:
            for successor in successors[block]:
                earliest[successor] = max(earliest[successor], earliest[block] + 1)
        period = max((earliest[block] + trailing[block] for block in sequence), default=1)
    latest = {block: period - distance for block, distance in trailing.items()}
    for block in reversed(sequence):
        for successor in successors[block]:
            latest[block] = min(latest[block], latest[successor] - 1)
        if latest[block] < lower[block]:
            return None
    return BlockConstraints(sequence, predecessors, lower, latest, period)


def prepare_dummy_blocks(
    graph: SubdividedGraph,
    order: Layers,
    winding: Winding,
    *,
    split: bool,
) -> tuple[dict[Node, Node], BlockConstraints]:
    groups = build_dummy_blocks(graph)
    if not split:
        block_of = {node: group[0] for group in groups for node in group}
        constraints = _block_constraints(order, block_of, None)
        if constraints is None:
            raise UnsplitBlockOrderError(
                "ダミー列を分割しない座標割当では層内順序の制約が循環します。"
                " --coordinate-method brandes_koepf_blocks で分割を許可できます。"
            )
        return block_of, constraints

    period = max(1, max(map(len, order.values()), default=0))
    block_of = {node: node for nodes in order.values() for node in nodes}
    joins = [
        (u, v)
        for block in groups
        for u, v in zip(block, block[1:])
        if winding.get((u, v), 0) == 0
    ]
    for u, v in joins:
        block_of[v] = block_of[u]
    constraints = _block_constraints(order, block_of, period)
    if constraints is None:
        # Keep consecutive runs aligned wherever their equality is feasible.
        block_of = {node: node for node in block_of}
        for u, v in joins:
            block_of[v] = block_of[u]
            if _block_constraints(order, block_of, period) is None:
                block_of[v] = v
        constraints = _block_constraints(order, block_of, period)
    if constraints is None:
        raise RuntimeError("could not satisfy block coordinate constraints")
    return block_of, constraints


def place_dummy_blocks(
    graph: SubdividedGraph,
    initial: Positions,
    min_gap: float,
    block_of: dict[Node, Node],
    constraints: BlockConstraints,
) -> Positions:
    if not initial:
        return {}
    targets: dict[Node, list[float]] = defaultdict(list)
    for node, (_, y) in initial.items():
        targets[block_of[node]].append(y / min_gap)
    coordinates: dict[Node, float] = {}
    for block in constraints.order:
        values = targets[block]
        lower = max([constraints.lower[block]] + [
            coordinates[other] + 1 for other in constraints.predecessors[block]
        ])
        coordinates[block] = min(constraints.latest[block], max(lower, sum(values) / len(values)))

    # For wide periods the renderer's cut can fall inside the rank bounds.
    # Translate all blocks together to keep every coordinate in the drawing.
    y_min, y_max = vertical_bounds(constraints.period, max(map(len, graph.layers.values())))
    lower, upper = min(coordinates.values()), max(coordinates.values())
    shift = (y_min + y_max - lower - upper) / 2 if lower <= y_min or upper >= y_max else 0.0
    return {
        node: (x, (coordinates[block_of[node]] + shift) * min_gap)
        for node, (x, _) in initial.items()
    }
