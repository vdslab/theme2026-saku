"""Block sifting on cyclic layers, adapted from Bachmaier et al. (2011), §5.4."""

from collections import defaultdict
from itertools import chain, combinations, product

from ..models import Edge, Layers, Node, SubdividedGraph, Winding
from .lib.crossings import crossings_between_edges, pair_positions
from .lib.embedding import edges_by_directed_strip, map_node_layers


def sift_blocks(
    graph: SubdividedGraph, initial_order: Layers, layers: list[int], rounds: int,
) -> tuple[Layers, Winding]:
    """Sift a shared circular ordering of original vertices and dummy chains.

    Internal segments use zero vertical winding at the shared cut. For each
    trial block position, enumerate the partings of its incident outer edges
    within each affected strip; all other windings remain fixed.
    """
    edges = list(graph.graph.edges)
    winding = dict.fromkeys(edges, 0)
    if len(layers) < 2:
        return initial_order, winding

    blocks = _build_blocks(graph)
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
            positions = block_layers[block]
            affected = by_block.get(block)
            if not affected:
                continue
            best_score = sum(_strip_score(order, winding, pair, strips[pair], set(), moving=moving)[0]
                             for pair, moving in affected.items())
            if best_score == 0:
                continue
            best = None
            remaining = [member for member in sequence if member != block]
            variable = {pair: moving & outer for pair, moving in affected.items()}
            visited = set()
            for index in range(len(sequence)):
                candidate = remaining[:index] + [block] + remaining[index:]
                rank = {member: i for i, member in enumerate(candidate)}
                orders = {layer: sorted(order[layer], key=lambda node: rank[node_block[node]])
                          for layer in positions}
                signature = tuple(tuple(nodes) for nodes in orders.values())
                if signature in visited:
                    continue
                visited.add(signature)
                trial = order | orders
                score, offsets = 0, {}
                for pair, moving in affected.items():
                    cost, selected = _strip_score(
                        trial, winding, pair, strips[pair], variable[pair],
                        outgoing=pair[0] in positions, moving=moving,
                    )
                    score += cost
                    offsets.update(selected)
                if score < best_score:
                    best_score, best = score, (candidate, orders, offsets)
                    if score == 0:
                        break
            if best is not None:
                sequence, orders, offsets = best
                order.update(orders)
                winding.update(offsets)
                improved = True
        if not improved:
            break
    return order, winding


def _build_blocks(graph: SubdividedGraph) -> list[tuple[Node, ...]]:
    dummy = graph.dummy_nodes
    following: dict[Node, Node] = {}
    incoming: dict[Node, Node] = {}
    for u, v in dict.fromkeys(graph.graph.edges):
        if u in dummy:
            if u in following:
                raise ValueError("global sifting requires nonbranching dummy paths")
            following[u] = v
        if v in dummy:
            if v in incoming:
                raise ValueError("global sifting requires nonbranching dummy paths")
            incoming[v] = u
    if following.keys() != dummy or incoming.keys() != dummy:
        raise ValueError("global sifting requires complete dummy paths")

    blocks = [(node,) for node in graph.original_nodes]
    for head in graph.graph.nodes:
        if head not in dummy or incoming[head] in dummy:
            continue
        path = [head]
        while following[path[-1]] in dummy:
            path.append(following[path[-1]])
        blocks.append(tuple(path))
    if sum(map(len, blocks)) != len(graph.graph.nodes):
        raise ValueError("global sifting requires dummy paths between original vertices")
    return blocks


def _strip_score(
    order: Layers, winding: Winding, pair: tuple[int, int],
    segments: list[Edge], variable: set[Edge], *,
    outgoing: bool = False, moving: set[Edge] | None = None,
) -> tuple[int, Winding]:
    start, end = pair_positions(order, *pair)
    fixed = [edge for edge in segments if edge not in variable]
    if moving is None:
        moving = set(segments)
    changed = [edge for edge in fixed if edge in moving]
    stable = [edge for edge in fixed if edge not in moving]
    # Two edges disjoint from the block keep their relative endpoint order.
    score = sum(crossings_between_edges(a, b, start, end, winding)
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
    costs = {}
    for value in (-1, 0, 1):
        tentative = winding | dict.fromkeys(variable, sign * value)
        costs[value] = [
            sum(crossings_between_edges(edge, other, start, end, tentative)
                for edge in group for other in fixed)
            for group in ordered
        ]

    # Within a parting, the variable edges share their moved endpoint and
    # never cross one another. Scan the split by updating its fixed-edge cost.
    moving_outer = [edge for edge in segments if edge in variable]
    original = sum(crossings_between_edges(a, b, start, end, winding)
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
