"""Exact integer squared-span descent for a fixed set of wrapped arcs."""

import networkx as nx


def minimize_square_ranks(graph, layers, assignment, *, scaled=False):
    ranks = assignment.node_to_layer.copy()
    arcs = tuple(
        (v, u, layers) if assignment.torus_flags[u, v] else (u, v, 0)
        for u, v in graph.edges
    )
    iterations = 0

    def best_step(step):
        source, sink = object(), object()
        cut = nx.DiGraph()
        cut.add_nodes_from((*graph.nodes, source, sink))
        unary = dict.fromkeys(graph.nodes, 0)
        forbidden = []

        def add(u, v, capacity):
            previous = cut.get_edge_data(u, v, {}).get("capacity", 0)
            cut.add_edge(u, v, capacity=previous + capacity)

        for u, v, shift in arcs:
            distance = ranks[v] - ranks[u]
            slope = 2 * step * (distance - shift)
            unary[u] -= slope
            unary[v] += slope
            add(u, v, step * step)
            add(v, u, step * step)
            if distance <= abs(step):
                forbidden.append((u, v) if step > 0 else (v, u))
        # The empty move costs the total capacity leaving source.
        constant = sum(min(0, cost) for cost in unary.values())
        hard = 1 - constant
        for node, cost in unary.items():
            if cost > 0:
                add(node, sink, cost)
            elif cost < 0:
                add(source, node, -cost)
            if not 0 <= ranks[node] + step < layers:
                add(node, sink, hard)
        for u, v in forbidden:
            add(u, v, hard)
        value, (selected, _) = nx.minimum_cut(cut, source, sink)
        return value + constant, selected - {source}

    scale = 1 << max(0, (layers - 1).bit_length() - 1) if scaled else 1
    while scale:
        while True:
            up, higher = best_step(scale)
            down, lower = best_step(-scale)
            if up >= 0 and down >= 0:
                break
            step, selected = (scale, higher) if up <= down else (-scale, lower)
            for node in selected:
                ranks[node] += step
            iterations += 1
        # The final unit-scale check certifies optimality. A better assignment
        # would decompose into feasible signed threshold moves whose span
        # changes on each arc have one sign, contradicting convexity.
        scale //= 2
    return ranks, iterations
