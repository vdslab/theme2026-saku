"""Certificates for wrap-count bounds without a full-size integer model."""

from random import Random

import networkx as nx

from layout_common.cycle_removal import remove_cycles
from sugiyama_layout.layer_assignment import assign_layers
from torus_layout.models import LayerAssignmentResult


def pack_cycles(graph, seeds=(0, 1, 2)):
    best = []
    for seed in seeds:
        rng = Random(seed)
        edges = rng.sample(graph.edges, len(graph.edges))
        residual = nx.DiGraph(edges)
        cycles = []
        while True:
            try:
                cycle = nx.find_cycle(residual)
            except nx.NetworkXNoCycle:
                break
            cycles.append(cycle)
            residual.remove_edges_from(cycle)
        if len(cycles) > len(best):
            best = cycles

    used = set()
    original = set(graph.edges)
    for cycle in best:
        if any(v != next_u for (_, v), (next_u, _) in zip(cycle, cycle[1:] + cycle[:1])):
            raise AssertionError("Packing contains a non-cycle")
        if len(set(cycle)) != len(cycle) or not set(cycle) <= original - used:
            raise AssertionError("Packing has missing or overlapping arcs")
        used.update(cycle)
    return best


def feasible_wrap_assignment(graph, seeds=(0, 1, 2, 3, 4)):
    best = None
    for seed in seeds:
        order = Random(seed).sample(graph.nodes, len(graph.nodes))
        result = remove_cycles(order, graph.edges)
        ranks = assign_layers(graph.nodes, result.edges)
        flags = {edge: edge in result.reversed_edges for edge in graph.edges}
        if any(flags[u, v] != (ranks[u] > ranks[v]) or ranks[u] == ranks[v] for u, v in graph.edges):
            raise AssertionError("Feasible order does not realize the reported wrap set")
        key = len(result.reversed_edges), max(ranks.values()) + 1
        if best is None or key < best[0]:
            best = key, LayerAssignmentResult(ranks, flags, 0)
    return best


def improve_wrap_assignment(graph, assignment, sweeps=4):
    """Strict single-vertex insertion descent in a feasible ordering."""
    order = sorted(graph.nodes, key=assignment.node_to_layer.__getitem__)
    successors = {node: set() for node in order}
    predecessors = {node: set() for node in order}
    for u, v in graph.edges:
        successors[u].add(v)
        predecessors[v].add(u)

    for _ in range(sweeps):
        changed = False
        for node in tuple(order):
            position = order.index(node)
            rest = order[:position] + order[position + 1:]
            # At the left end, only incoming arcs are backward.
            score = len(predecessors[node])
            current = score
            best, index = score, 0
            for i, other in enumerate(rest, 1):
                score += (other in successors[node]) - (other in predecessors[node])
                if i == position:
                    current = score
                if score < best:
                    best, index = score, i
            if best < current:
                order = rest[:index] + [node] + rest[index:]
                changed = True
        if not changed:
            break

    positions = {node: i for i, node in enumerate(order)}
    flags = {(u, v): positions[u] > positions[v] for u, v in graph.edges}
    forward = [(v, u) if flags[u, v] else (u, v) for u, v in graph.edges]
    return LayerAssignmentResult(assign_layers(graph.nodes, forward), flags, 0)


def pack_short_return_cycles(graph, flags, seeds=(0, 1, 2)):
    """Start each cycle on a backward arc and find its shortest residual return."""
    backwards = [edge for edge in graph.edges if flags[edge]]
    best = []
    for seed in seeds:
        rng = Random(seed)
        residual = nx.DiGraph(rng.sample(graph.edges, len(graph.edges)))
        cycles = []
        for u, v in rng.sample(backwards, len(backwards)):
            if not residual.has_edge(u, v):
                continue
            try:
                path = nx.shortest_path(residual, v, u)
            except nx.NetworkXNoPath:
                continue
            cycle = [(u, v), *zip(path, path[1:])]
            cycles.append(cycle)
            residual.remove_edges_from(cycle)
        if len(cycles) > len(best):
            best = cycles
    return best
