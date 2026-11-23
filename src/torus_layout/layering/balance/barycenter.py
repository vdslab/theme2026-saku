"""固定されたトーラス辺のフラグを維持する重心法。"""

from ... import constants

from time import perf_counter
from collections import defaultdict
from ...models import Node, Edge, Weights, LayerAssignmentResult
from .diff import optimize_diff


def optimize_barycenter(
    V: list[Node],
    A: list[Edge],
    torus_count: int,
    layer_count: int,
    w: Weights,
    lam: dict[Edge, int],
) -> LayerAssignmentResult:
    """diffの初期解から、元と同じ反復・補正で重心を整える。"""
    max_layer_bound = layer_count - 1
    initial = optimize_diff(V, A, torus_count, layer_count, w, lam)
    if not initial.node_to_layer:
        return initial
    y_val, t_val = initial.node_to_layer, initial.torus_flags
    start_time = perf_counter()
    for u, v in A:
        if not t_val[u, v] and y_val[u] == y_val[v]:
            if y_val[v] < max_layer_bound:
                y_val[v] += 1
            elif y_val[u] > 0:
                y_val[u] -= 1
    in_edges: dict[Node, list[Node]] = defaultdict(list)
    out_edges: dict[Node, list[Node]] = defaultdict(list)
    for u, v in A:
        in_edges[v].append(u)
        out_edges[u].append(v)
    threshold = constants.BARYCENTER_THRESHOLD
    max_iterations = constants.BARYCENTER_MAX_ITERATIONS
    iteration = 0
    while iteration < max_iterations:
        total_change = 0.0
        new_y_val = y_val.copy()
        for v in V:
            if v in in_edges and len(in_edges[v]) > 0:
                min_layer = max((y_val[u] for u in in_edges[v])) + 1
            else:
                min_layer = 0
            if v in out_edges and len(out_edges[v]) > 0:
                max_layer = min((y_val[u] for u in out_edges[v])) - 1
            else:
                max_layer = max_layer_bound
            min_layer = max(min_layer, 0)
            max_layer = min(max_layer, max_layer_bound)
            if min_layer > max_layer:
                continue
            all_neighbors: list[Node] = []
            if v in in_edges:
                all_neighbors.extend(in_edges[v])
            if v in out_edges:
                all_neighbors.extend(out_edges[v])
            if len(all_neighbors) == 0:
                continue
            center = sum((y_val[u] for u in all_neighbors)) / len(all_neighbors)
            candidate_layer = round(center)
            candidate_layer = max(min_layer, min(max_layer, candidate_layer))
            if any((y_val[u] == candidate_layer for u in all_neighbors)):
                found = False
                for offset in range(1, max_layer - min_layer + 2):
                    upper = candidate_layer + offset
                    if upper <= max_layer and (
                        not any((y_val[u] == upper for u in all_neighbors))
                    ):
                        candidate_layer = upper
                        found = True
                        break
                    lower = candidate_layer - offset
                    if lower >= min_layer and (
                        not any((y_val[u] == lower for u in all_neighbors))
                    ):
                        candidate_layer = lower
                        found = True
                        break
                if not found:
                    candidate_layer = y_val[v]
            best_layer = candidate_layer
            total_change += abs(best_layer - y_val[v])
            new_y_val[v] = best_layer
        y_val = new_y_val
        for u, v in A:
            if not t_val[u, v] and y_val[u] == y_val[v]:
                if v in out_edges and len(out_edges[v]) > 0:
                    min_v_layer = min((y_val[w] for w in out_edges[v]))
                    if y_val[v] + 1 < min_v_layer:
                        y_val[v] += 1
                        continue
                if u in in_edges and len(in_edges[u]) > 0:
                    max_u_layer = max((y_val[w] for w in in_edges[u]))
                    if y_val[u] - 1 > max_u_layer:
                        y_val[u] -= 1
                        continue
                if y_val[v] < max_layer_bound:
                    y_val[v] += 1
                elif y_val[u] > 0:
                    y_val[u] -= 1
        iteration += 1
        if total_change < threshold:
            break
    return LayerAssignmentResult(
        y_val, t_val, initial.runtime + perf_counter() - start_time,
        initial.solver_status, initial.solver_time,
    )
