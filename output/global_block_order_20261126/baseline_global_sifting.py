"""Block sifting on cyclic layers, adapted from Bachmaier et al. (2011), §5.4."""

from collections import defaultdict
from collections.abc import Callable, Iterator
from itertools import chain, combinations, product

from ..models import Edge, Layers, Node, SubdividedGraph, Winding
from ..subdivision import build_dummy_blocks
from .lib.crossings import crossings_between_edges, pair_positions
from .lib.embedding import edges_by_directed_strip, map_node_layers


def sift_blocks(
    graph: SubdividedGraph, initial_order: Layers, layers: list[int], rounds: int,
    *, sparse_candidates: bool = False, local_winding: bool = False, integer_scoring: bool = False,
    should_stop: Callable[[], bool] | None = None,
    cache_strip_scores: bool = False, incremental_orders: bool = False,
    incremental_scores: bool = False,
) -> tuple[Layers, Winding]:
    """Sift a shared circular ordering of original vertices and dummy chains.

    Internal segments use zero vertical winding at the shared cut. For each
    trial block position, enumerate the partings of its incident outer edges
    within each affected strip; all other windings remain fixed.
    A stop request returns the last committed block order and windings.
    """
    edges = list(graph.graph.edges)
    winding = dict.fromkeys(edges, 0)
    if len(layers) < 2:
        return initial_order, winding

    blocks = build_dummy_blocks(graph)
    if any(len(nodes) >= len(layers) for nodes in blocks):
        raise ValueError("global sifting requires original edge spans of at most one horizontal period")
    node_block = {node: block for block, nodes in enumerate(blocks) for node in nodes}
    node_layer = map_node_layers(initial_order)
    block_layers = [{node_layer[node]: node for node in nodes} for nodes in blocks]
    if any(len(positions) != len(nodes) for nodes, positions in zip(blocks, block_layers)):
        raise ValueError("global sifting requires at most one vertex per block in each layer")

    # Use the barycenter order to seed a single list; restricting this list
    # to each layer keeps all blocks in a consistent relative order.
    sequence = list(dict.fromkeys(node_block[node] for nodes in initial_order.values() for node in nodes))
    rank = {block: i for i, block in enumerate(sequence)}
    order = {layer: sorted(initial_order[layer], key=lambda node: rank[node_block[node]])
             for layer in layers}
    strips = edges_by_directed_strip(order, layers, edges)
    if sum(map(len, strips.values())) != len(edges):
        raise ValueError("global sifting requires edges between consecutive cyclic layers")
    dummy = graph.dummy_nodes
    outer = {edge for edge in edges if not all(node in dummy for node in edge)}
    by_block: dict[int, dict[tuple[int, int], set[Edge]]] = defaultdict(lambda: defaultdict(set))
    for pair, segments in strips.items():
        for edge in segments:
            for node in edge:
                by_block[node_block[node]][pair].add(edge)

    for _ in range(rounds):
        improved = False
        for block in tuple(sequence):
            if should_stop is not None and should_stop():
                return order, winding
            positions = block_layers[block]
            affected = by_block.get(block)
            if not affected:
                continue
            best_score = sum(_strip_score(order, winding, pair, strips[pair], set(), moving=moving,
                                          integer_scoring=integer_scoring)[0]
                             for pair, moving in affected.items())
            if best_score == 0:
                continue
            best = None
            remaining = [member for member in sequence if member != block]
            variable = {pair: moving & outer for pair, moving in affected.items()}
            strip_cache: dict[tuple[tuple[int, int], int, int], tuple[int, Winding]] = {}
            score_cache: dict[tuple[int, int], tuple[int, Winding]] = {}
            previous_orders: Layers = {}
            running_score = 0
            for index, orders in _trial_orders(
                order, positions, block, remaining, node_block, sparse_candidates, incremental_orders,
            ):
                if should_stop is not None and should_stop():
                    return order, winding
                trial = order | orders
                score, offsets = 0, {}
                if incremental_scores:
                    touched = {layer for layer, nodes in orders.items()
                               if nodes is not previous_orders.get(layer)}
                    previous_orders = orders
                    pairs = (pair for pair in affected
                             if pair not in score_cache or pair[0] in touched or pair[1] in touched)
                else:
                    pairs = iter(affected)
                for pair in pairs:
                    moving = affected[pair]
                    cached = None
                    if cache_strip_scores:
                        left, right = pair
                        key = (pair, trial[left].index(positions[left]) if left in positions else -1,
                               trial[right].index(positions[right]) if right in positions else -1)
                        cached = strip_cache.get(key)
                    if cached is None:
                        cached = _strip_score(
                            trial, winding, pair, strips[pair], variable[pair],
                            outgoing=pair[0] in positions, moving=moving, local_winding=local_winding,
                            integer_scoring=integer_scoring,
                        )
                        # Orders of stationary vertices and their windings are
                        # invariant until this block move is committed.
                        if cache_strip_scores:
                            strip_cache[key] = cached
                    cost, selected = cached
                    if incremental_scores:
                        running_score += cost - score_cache.get(pair, (0, {}))[0]
                        score_cache[pair] = cached
                    else:
                        score += cost
                        offsets.update(selected)
                if incremental_scores:
                    score = running_score
                if score < best_score:
                    if incremental_scores:
                        offsets = {edge: value for pair in affected
                                   for edge, value in score_cache[pair][1].items()}
                    best_score, best = score, (index, orders, offsets)
                    if score == 0:
                        break
            if best is not None:
                index, orders, offsets = best
                sequence = remaining[:index] + [block] + remaining[index:]
                order.update(orders)
                winding.update(offsets)
                improved = True
        if not improved:
            break
    return order, winding


def _trial_orders(
    order: Layers, positions: dict[int, Node], block: int, remaining: list[int],
    node_block: dict[Node, int], sparse: bool, incremental: bool = False,
) -> Iterator[tuple[int, Layers]]:
    if sparse:
        rank = {member: i for i, member in enumerate(remaining)}
        local_others = {layer: [node for node in order[layer] if node != moving]
                        for layer, moving in positions.items()}
        if incremental:
            changes: dict[int, list[int]] = defaultdict(list)
            for layer, nodes in local_others.items():
                for node in nodes:
                    changes[rank[node_block[node]] + 1].append(layer)
            offsets = dict.fromkeys(positions, 0)
            orders = {layer: [positions[layer], *nodes] for layer, nodes in local_others.items()}
            yield 0, orders.copy()
            for index, touched in sorted(changes.items()):
                for layer in touched:
                    offset = offsets[layer]
                    nodes = orders[layer]
                    orders[layer] = nodes[:offset] + [nodes[offset + 1], nodes[offset]] + nodes[offset + 2:]
                    offsets[layer] += 1
                yield index, orders.copy()
            return
        boundaries = {rank[node_block[node]] + 1 for nodes in local_others.values() for node in nodes}
        # Only passing a block present in a touched layer changes its local order.
        # The first index in each interval preserves the original tie-breaking.
        for index in (0, *sorted(boundaries)):
            orders = {}
            for layer, nodes in local_others.items():
                before = sum(rank[node_block[node]] < index for node in nodes)
                orders[layer] = nodes[:before] + [positions[layer]] + nodes[before:]
            yield index, orders
        return

    visited = set()
    for index in range(len(remaining) + 1):
        candidate = remaining[:index] + [block] + remaining[index:]
        rank = {member: i for i, member in enumerate(candidate)}
        orders = {layer: sorted(order[layer], key=lambda node: rank[node_block[node]])
                  for layer in positions}
        signature = tuple(tuple(nodes) for nodes in orders.values())
        if signature in visited:
            continue
        visited.add(signature)
        yield index, orders


def _integer_pair_terms(
    a: tuple[int, int, int], b: tuple[int, int, int],
) -> tuple[int, int]:
    x = (b[0] > a[0]) - (b[0] < a[0])
    y = (b[1] > a[1]) - (b[1] < a[1])
    return y - x, abs(x) + abs(y) - 2


def _strip_score(
    order: Layers, winding: Winding, pair: tuple[int, int],
    segments: list[Edge], variable: set[Edge], *,
    outgoing: bool = False, moving: set[Edge] | None = None,
    local_winding: bool = False, integer_scoring: bool = False,
    bulk_costs: Callable[[list[list[Edge]], list[Edge], dict[Node, int],
                          dict[Node, int], Winding, int], dict[int, list[int]]] | None = None,
) -> tuple[int, Winding]:
    start, end = pair_positions(order, *pair)
    fixed = [edge for edge in segments if edge not in variable]
    if moving is None:
        moving = set(segments)
    changed = [edge for edge in fixed if edge in moving]
    stable = [edge for edge in fixed if edge not in moving]
    if integer_scoring:
        indexed = {edge: (start[edge[0]], end[edge[1]], winding.get(edge, 0)) for edge in segments}

        def count(a: Edge, b: Edge) -> int:
            left, right = indexed[a], indexed[b]
            shift, correction = _integer_pair_terms(left, right)
            return max(0, (abs(2 * (right[2] - left[2]) + shift) + correction) // 2)
    else:
        def count(a: Edge, b: Edge) -> int:
            return crossings_between_edges(a, b, start, end, winding)

    # Two edges disjoint from the block keep their relative endpoint order.
    score = sum(count(a, b)
                for a, b in chain(combinations(changed, 2), product(changed, stable)))
    if not variable:
        return score, {}

    # Orient the parting towards the moved vertex. Offsets in that
    # orientation are nondecreasing in opposite-end order and differ by at
    # most one. Restore the sign for outgoing edges.
    axis = end if outgoing else start
    sign = -1 if outgoing else 1
    groups: dict[int, list[Edge]] = defaultdict(list)
    for edge in segments:
        if edge in variable:
            groups[axis[edge[1 if outgoing else 0]]].append(edge)
    ordered = [group for _, group in sorted(groups.items())]
    costs = {-1: [], 0: [], 1: []}
    if bulk_costs is not None:
        costs = bulk_costs(ordered, fixed, start, end, winding, sign)
    elif integer_scoring:
        for group in ordered:
            low = middle = high = 0
            for edge in group:
                left = indexed[edge]
                for other in fixed:
                    right = indexed[other]
                    shift, correction = _integer_pair_terms(left, right)
                    center = 2 * right[2] + shift
                    low += max(0, (abs(center + 2 * sign) + correction) // 2)
                    middle += max(0, (abs(center) + correction) // 2)
                    high += max(0, (abs(center - 2 * sign) + correction) // 2)
            costs[-1].append(low)
            costs[0].append(middle)
            costs[1].append(high)
    else:
        # Candidate scoring reads only variable and fixed edges in this strip.
        base = {edge: winding.get(edge, 0) for edge in fixed} if local_winding else winding
        for value in (-1, 0, 1):
            tentative = base | dict.fromkeys(variable, sign * value)
            costs[value] = [
                sum(crossings_between_edges(edge, other, start, end, tentative)
                    for edge in group for other in fixed)
                for group in ordered
            ]

    # Within a parting, the variable edges share their moved endpoint and
    # never cross one another. Scan the split by updating its fixed-edge cost.
    moving_outer = [edge for edge in segments if edge in variable]
    original = sum(count(a, b)
                   for a, b in chain(combinations(moving_outer, 2), product(moving_outer, fixed)))
    best = (original, sum(abs(winding[edge]) for edge in moving_outer))
    chosen = (0, 0)
    for low in (-1, 0):
        total = sum(costs[low + 1])
        winding_cost = abs(low + 1) * sum(map(len, ordered))
        if (total, winding_cost) < best:
            best, chosen = (total, winding_cost), (low, 0)
        for index, (left, right) in enumerate(zip(costs[low], costs[low + 1]), 1):
            total += left - right
            winding_cost += (abs(low) - abs(low + 1)) * len(ordered[index - 1])
            if (total, winding_cost) < best:
                best, chosen = (total, winding_cost), (low, index)
    if best[0] == original:
        return score + original, {}
    low, split = chosen
    offsets = {edge: sign * (low + (i >= split))
               for i, group in enumerate(ordered) for edge in group}
    return score + best[0], offsets
