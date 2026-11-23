"""Experiments built on the current torus implementation and two repository baselines."""

from collections import Counter
from contextlib import contextmanager
from itertools import permutations, product
from math import ceil, dist, sqrt
from statistics import pvariance
from time import perf_counter
from unittest.mock import patch

import gurobipy as gp
from matplotlib import pyplot as plt
from PIL import Image

from torus_layout import constants
from torus_layout.coordinates import assign_coordinates
from torus_layout.coordinates import api as coordinate_api
from torus_layout.coordinates import brandes_koepf as bk
from torus_layout.coordinates.periodic import drawing_period, smooth_torus_edges
from torus_layout.crossing import count_crossings, count_seam_segments, optimize_seam, reduce_crossings
from torus_layout.crossing.lib.crossings import count_all_crossings
from torus_layout.crossing.initialization import initial_orders
from torus_layout.crossing.lib.embedding import (
    base_order, compute_winding_numbers, copy_order, forward_layer_pairs,
    postprocess_sifting_rotations,
)
from torus_layout.crossing.sifting import run_sifting_with_global_guard, sift_two_layer_pair
from torus_layout.crossing.unwind import unwind_levels
from torus_layout.drawing import DrawingOptions, create_figure
from torus_layout.drawing import artists
from torus_layout.drawing.output import output_figure
from torus_layout.domain import vertical_bounds
from torus_layout.layering import balance_layers, find_minimum_configuration
from torus_layout.layering import search as search_module
from torus_layout.layering.minimize_wraps import minimize_torus_edges, solve_fixed_layers
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.models import CoordinateResult, CrossingResult, LayerAssignmentResult
from torus_layout.pipeline import run_pipeline
from torus_layout.subdivision import insert_dummy_nodes
from old_torus_layout.lib.insert_dummy_node import insert_dummy_node as legacy_subdivision

from .geometry import Route, crossing_metrics as geometric_crossing_metrics, planar_route, route_metrics, torus_routes

BALANCE = constants.DEFAULT_BALANCE_METHOD
ROUNDS = constants.DEFAULT_ROUNDS


@contextmanager
def record_solver(args, trace):
    """Keep production callers and record each model before its context closes."""
    original = gp.Model

    @contextmanager
    def measured_model(*positional, **keywords):
        with original(*positional, **keywords) as model:
            model.Params.Threads = 1
            model.Params.Seed = 0
            model.Params.TimeLimit = args.solver_seconds
            started = perf_counter()
            try:
                yield model
            finally:
                record = {"name": model.ModelName, "status": model.Status,
                          "solutions": model.SolCount, "seconds": perf_counter() - started}
                if model.SolCount:
                    record["objective"] = model.ObjVal
                if model.Status not in (gp.GRB.LOADED, gp.GRB.INFEASIBLE) and model.IsMIP:
                    try:
                        bound = model.ObjBound
                    except (AttributeError, gp.GurobiError):
                        pass
                    else:
                        if abs(bound) < gp.GRB.INFINITY:
                            record["bound"] = bound
                trace.append(record)

    def counted_candidate(nodes, edges, layer_count, *positional, **keywords):
        before = len(trace)
        try:
            return solve_fixed_layers(nodes, edges, layer_count, *positional, **keywords)
        finally:
            if len(trace) > before:
                trace[-1]["candidate_layers"] = layer_count

    with use_local_license(args.local_license), patch.object(gp, "Model", measured_model), patch.object(
        search_module, "solve_fixed_layers", counted_candidate
    ):
        yield


def attempt_time(fn, *args, **kwargs):
    started = perf_counter()
    value = fn(*args, **kwargs)
    return value, perf_counter() - started


def assignment_metrics(graph, assignment, n_layers, required_wraps):
    ranks, flags = assignment.node_to_layer, assignment.torus_flags
    if set(ranks) != set(graph.nodes) or set(flags) != set(graph.edges):
        raise ValueError("incomplete assignment")
    spans = [ranks[v] - ranks[u] + n_layers * int(flags[u, v]) for u, v in graph.edges]
    sizes = Counter(ranks.values())
    wraps = sum(flags.values())
    violations = sum(s < 1 or s >= n_layers for s in spans)
    violations += sum(not 0 <= r < n_layers for r in ranks.values())
    violations += required_wraps is not None and wraps != required_wraps
    return {
        "layers": n_layers, "occupied_layers": len(sizes), "rank_wrap_edges": wraps,
        "assignment_violations": violations, "span_sum": sum(spans),
        "span_square_sum": sum(s*s for s in spans), "max_span": max(spans, default=0),
        "predicted_dummies": sum(s - 1 for s in spans),
        "layer_max_size": max(sizes.values()), "layer_size_variance": pvariance(
            sizes[i] for i in range(n_layers)
        ),
    }


def chains_for(graph, subdivided):
    """Trace the ordered subdivision output, validating ownership and endpoints."""
    children = iter(subdivided.graph.edges)
    originals = set(graph.nodes)
    used_dummies = set()
    paths = {}
    for source, target in graph.edges:
        chain = [source]
        while True:
            segment = next(children, None)
            if segment is None or segment[0] != chain[-1]:
                raise ValueError("broken edge chain")
            node = segment[1]
            chain.append(node)
            if node in originals:
                if node != target:
                    raise ValueError("incorrect original endpoint")
                break
            if node in used_dummies:
                raise ValueError("dummy shared by two segments entering it")
            used_dummies.add(node)
        paths[source, target] = chain
    if next(children, None) is not None or used_dummies != subdivided.dummy_nodes:
        raise ValueError("unexpected subdivision output")
    return paths


def subdivision_metrics(graph, subdivided):
    paths = chains_for(graph, subdivided)
    layers = {node: i for i, key in enumerate(sorted(subdivided.layers))
              for node in subdivided.layers[key]}
    period = len(subdivided.layers)
    bad = sum(layers[v] - layers[u] + period * subdivided.torus_flags[u, v] != 1
              for u, v in subdivided.graph.edges)
    return paths, {
        "dummy_nodes": len(subdivided.dummy_nodes), "proper_edges": len(subdivided.graph.edges),
        "unit_span_violations": bad, "max_proper_layer_size": max(map(len, subdivided.layers.values())),
    }


def prepared(graph):
    search = find_minimum_configuration(graph)
    if search.layer_count is None or search.torus_count is None:
        raise ValueError("layer search failed")
    assignment = balance_layers(graph, search.torus_count, search.layer_count, BALANCE)
    metrics = assignment_metrics(graph, assignment, search.layer_count, search.torus_count)
    if metrics["assignment_violations"]:
        raise ValueError("invalid default assignment")
    subdivided = insert_dummy_nodes(graph, assignment)
    paths, metrics = subdivision_metrics(graph, subdivided)
    if metrics["unit_span_violations"]:
        raise ValueError("invalid default subdivision")
    return search, assignment, subdivided, paths


def fixed_count(graph, layers):
    ranks, flags, _, _, wraps = minimize_torus_edges(list(graph.nodes), list(graph.edges), layers)
    if wraps is None:
        return None
    return LayerAssignmentResult(ranks, flags, 0), wraps


def from_assignment(graph, assignment, *, geometry=True):
    subdivided = insert_dummy_nodes(graph, assignment)
    paths, metrics = subdivision_metrics(graph, subdivided)
    if metrics["unit_span_violations"]:
        return {**metrics, "status": "invalid_subdivision"}
    crossing = reduce_crossings(subdivided)
    coords = assign_coordinates(subdivided, crossing)
    routes, bounds = torus_routes(paths, subdivided, crossing, coords)
    return {**metrics, "embedding_crossings": count_crossings(subdivided, crossing),
            **route_metrics(routes, bounds, geometry=geometry)}


def layer_study(graph, run):
    def search():
        result = find_minimum_configuration(graph)
        if result.layer_count is None:
            return {"status": "no_solution"}, None
        return {"layers": result.layer_count, "rank_wrap_edges": result.torus_count}, result

    solution = run("search", "binary", "fixed_sqrt", search)
    binary_seconds = run.outcome["wall_seconds"]

    def fixed():
        layers = ceil(sqrt(2 * len(graph.nodes)))
        result = fixed_count(graph, layers)
        if result is None:
            return {"status": "no_solution", "layers": layers}, None
        _, wraps = result
        return {"layers": layers, "rank_wrap_edges": wraps}, (layers, wraps)

    fixed_result = run("search", "fixed_sqrt", "fixed_sqrt", fixed)
    fixed_seconds = run.outcome["wall_seconds"]
    if solution is None:
        return
    layers, wraps = solution.layer_count, solution.torus_count

    def evaluate(method, expected_l=layers, expected_t=wraps):
        if method == "feasible":
            fixed_solution = fixed_count(graph, expected_l)
            if fixed_solution is None:
                return {"status": "no_solution"}, None
            assignment, _ = fixed_solution
        else:
            assignment = balance_layers(graph, expected_t, expected_l, method)
        if not assignment.node_to_layer:
            return {"status": "no_solution"}, None
        metrics = assignment_metrics(graph, assignment, expected_l, expected_t)
        if metrics["assignment_violations"]:
            metrics["status"] = "invalid_assignment"
        return metrics, assignment

    def assess_downstream(experiment, variant, baseline, assignment):
        metrics = run.outcome
        if assignment is not None and metrics.get("status", "ok") == "ok":
            run(experiment, variant, baseline, lambda: (from_assignment(graph, assignment), None))

    for method in ("feasible", "diff", "diff_square", "qp", "barycenter"):
        assignment = run("balance", method, "diff", lambda: evaluate(method))
        assess_downstream("balance_downstream", method, "diff", assignment)

    for name, rank_config, search_seconds in (
        ("default", (layers, wraps), binary_seconds),
        ("fixed_sqrt", fixed_result, fixed_seconds),
        ("double_layers", (min(len(graph.nodes), 2 * layers), wraps), binary_seconds),
    ):
        if rank_config is None:
            continue

        def whole():
            (metrics, assignment), seconds = attempt_time(evaluate, BALANCE, *rank_config)
            return {**metrics, "layer_step_seconds": search_seconds + seconds}, assignment

        assignment = run("layering_step", name, "default", whole)
        assess_downstream("layering_downstream", name, "default", assignment)


def subdivision_study(graph, run):
    state = run("input", "default", "default", lambda: ({}, prepared(graph)))
    if state is None:
        return
    search, assignment, _, _ = state
    explicit = {i: assignment.layers.get(i, []) for i in range(search.layer_count)}
    legacy = run(
        "subdivision", "legacy_lookup", "legacy_lookup",
        lambda: ({}, legacy_subdivision(list(graph.nodes), list(graph.edges), assignment.layers,
                                       assignment.torus_flags)),
    )

    def compare(layer_map):
        result = insert_dummy_nodes(graph, assignment, layers=layer_map)
        value = (list(result.graph.nodes), list(result.graph.edges), result.layers,
                 result.torus_flags, result.weights)
        return {}, (result, value)

    for name, layer_map in (("current_lookup", None), ("explicit_empty_layers", explicit)):
        baseline = "current_lookup" if layer_map is not None else "legacy_lookup"
        data = run("subdivision", name, baseline, lambda: compare(layer_map))
        if data is None:
            continue
        result, value = data
        _, metrics = subdivision_metrics(graph, result)
        expected = assignment_metrics(graph, assignment, search.layer_count, search.torus_count)
        metrics["dummy_count_matches_rank_span"] = metrics["dummy_nodes"] == expected["predicted_dummies"]
        metrics["matches_legacy"] = legacy is not None and value == legacy
        run("subdivision_checks", name, "current_lookup", lambda: (metrics, None))


def copied(crossing):
    return CrossingResult(copy_order(crossing.order), dict(crossing.winding_numbers))


def initialize(graph, use_barycenter):
    layers, edges = sorted(graph.layers), list(graph.graph.edges)
    if use_barycenter:
        order = initial_orders(graph.layers, layers, edges)[0]
    else:
        order = base_order(graph.layers, layers)
    return CrossingResult(order, compute_winding_numbers(edges, order, graph.layers, layers))


def sift(graph, start, rounds, *, guard=True, winding=True):
    result = copied(start)
    layers, edges = sorted(graph.layers), list(graph.graph.edges)
    if guard:
        run_sifting_with_global_guard(result.order, result.winding_numbers, layers, edges,
                                     rounds, graph.dummy_nodes, optimize_winding=winding)
    else:
        pairs = forward_layer_pairs(layers)
        for left, right in pairs + pairs[:-1]:
            for _ in range(rounds):
                sift_two_layer_pair(left, right, result.order, result.winding_numbers, edges,
                                    graph.dummy_nodes, optimize_winding=winding)
    return result


def rotate(graph, start, guard):
    result = copied(start)
    postprocess_sifting_rotations(result.order, result.winding_numbers, sorted(graph.layers),
                                  list(graph.graph.edges))
    if guard and count_crossings(graph, result) > count_crossings(graph, start):
        return start
    return result


def crossing_metrics(graph, crossing):
    y = {node: i / len(order) for order in crossing.order.values()
         for i, node in enumerate(order)}
    dy = [abs(y[v] - y[u] + crossing.winding_numbers.get((u, v), 0))
          for u, v in graph.graph.edges]
    dummy = graph.dummy_nodes
    inner = [(u, v) for u, v in graph.graph.edges if u in dummy and v in dummy]
    return {
        "embedding_crossings": count_crossings(graph, crossing),
        "inner_segment_crossings": count_all_crossings(
            crossing.order, crossing.winding_numbers, sorted(graph.layers), inner
        ),
        "seam_segments": count_seam_segments(graph, crossing),
        "winding_magnitude": sum(abs(crossing.winding_numbers.get(e, 0)) for e in graph.graph.edges),
        "angular_span_sum": sum(dy), "angular_span_max": max(dy, default=0),
    }


def cut_cost(graph, start):
    rank = {u: (layer, i) for layer, order in start.order.items() for i, u in enumerate(order)}

    def cost(gaps):
        return sum(
            start.winding_numbers.get((u, v), 0)
            + (rank[u][1] < gaps[rank[u][0]]) - (rank[v][1] < gaps[rank[v][0]]) != 0
            for u, v in graph.graph.edges
        )
    return cost


def greedy_cut(graph, start):
    cost = cut_cost(graph, start)
    gaps = dict.fromkeys(start.order, 0)
    for _ in range(10):
        before = cost(gaps)
        for layer, order in sorted(start.order.items()):
            gaps[layer] = min(range(max(1, len(order))), key=lambda i: cost({**gaps, layer: i}))
        if cost(gaps) == before:
            break
    shifts = {node: i < gaps[layer] for layer, order in start.order.items()
              for i, node in enumerate(order)}
    return CrossingResult(
        {k: v[gaps[k]:] + v[:gaps[k]] for k, v in start.order.items()},
        {e: start.winding_numbers.get(e, 0) + shifts[e[0]] - shifts[e[1]] for e in graph.graph.edges},
    )


def crossing_study(graph, run):
    state = run("input", "default", "default", lambda: ({}, prepared(graph)))
    if state is None:
        return
    _, _, sub, paths = state

    def evaluate(group, name, baseline, function):
        def compute():
            crossing, elapsed = attempt_time(function)
            return {"algorithm_seconds": elapsed, **crossing_metrics(sub, crossing)}, crossing
        return run(group, name, baseline, compute)

    for name, barycenter in (("input_order", False), ("circular_barycenter", True)):
        start = evaluate("initialization", name, "input_order", lambda: initialize(sub, barycenter))
        if start is not None:
            evaluate("initialization_then_sifting", name, "input_order",
                     lambda: sift(sub, start, ROUNDS))

    initial = initialize(sub, True)
    baseline = evaluate("sifting", "no_sifting", "no_sifting", lambda: initial)
    for name, rounds, guard, winding in (
        ("no_guard", ROUNDS, False, True), ("fixed_winding", ROUNDS, True, False),
        ("rounds_1", 1, True, True), ("default", ROUNDS, True, True),
        ("rounds_10", 10, True, True),
    ):
        result = evaluate("sifting", name, "no_sifting",
                          lambda: sift(sub, initial, rounds, guard=guard, winding=winding))
        if name == "default":
            baseline = result
    if baseline is None:
        return

    for name, func in (
        ("off", lambda: baseline), ("unguarded", lambda: rotate(sub, baseline, False)),
        ("guarded", lambda: rotate(sub, baseline, True)),
    ):
        evaluate("rotation", name, "off", func)
    rotated = rotate(sub, baseline, True)
    rotation_controls = (
        ("off", lambda: rotated),
        ("inner_only", lambda: unwind_levels(sub, rotated, include_non_inner=False)),
        ("full", lambda: unwind_levels(sub, rotated)),
    )
    for name, func in rotation_controls:
        evaluate("unwind", name, "off", func)
    for name, func in (
        ("off", lambda: rotated), ("greedy", lambda: greedy_cut(sub, rotated)),
        ("dp", lambda: optimize_seam(sub, rotated)),
    ):
        evaluate("seam", name, "off", func)

    def unwind_then_dp():
        return optimize_seam(sub, unwind_levels(sub, rotated))

    def early_and_late_unwind():
        early = unwind_then_dp()
        late = optimize_seam(sub, unwind_levels(sub, rotated, include_non_inner=False))
        late = optimize_seam(sub, unwind_levels(sub, late))
        return min((early, late), key=lambda result: count_seam_segments(sub, result))

    evaluate("unwind_dp_order", "unwind_first_only", "unwind_first_only", unwind_then_dp)
    evaluate("unwind_dp_order", "early_and_late", "unwind_first_only", early_and_late_unwind)

    for unwind, dp in product((False, True), repeat=2):
        name = f"unwind_{int(unwind)}_dp_{int(dp)}"

        def end_to_end():
            crossing, elapsed = attempt_time(reduce_crossings, sub, unwind=unwind, optimize_seams=dp)
            coords = assign_coordinates(sub, crossing)
            routes, bounds = torus_routes(paths, sub, crossing, coords)
            return {"algorithm_seconds": elapsed, **crossing_metrics(sub, crossing),
                    **route_metrics(routes, bounds)}, None

        run("crossing_step", name, "unwind_0_dp_0", end_to_end)


def uniform_coordinates(sub, crossing, iterations):
    period = drawing_period(crossing.order, 1.0)
    y = {u: (period - len(order)) / 2 + i for order in crossing.order.values()
         for i, u in enumerate(order)}
    if iterations:
        y = smooth_torus_edges(y, crossing.order, list(sub.graph.edges),
                               crossing.winding_numbers, period, 1.0, iterations)
    return CoordinateResult({u: (float(i), y[u]) for i, layer in enumerate(sorted(crossing.order))
                             for u in crossing.order[layer]}, period)


def coordinate_metrics(sub, crossing, coordinates):
    positions, period = coordinates.positions, coordinates.period
    lower, upper = vertical_bounds(period, max(map(len, crossing.order.values())))
    ys = [pos[1] for pos in positions.values()]
    gaps = []
    for order in crossing.order.values():
        values = [positions[node][1] for node in order]
        gaps.extend(b - a for a, b in zip(values, values[1:]))
        if values:
            gaps.append(values[0] + period - values[-1])
    dummy = sub.dummy_nodes
    inner = [(u, v) for u, v in sub.graph.edges if u in dummy and v in dummy]
    return {
        "period": period, "min_cyclic_gap": min(gaps, default=period),
        "order_violations": sum(gap <= 0 for gap in gaps),
        "gap_violations": sum(gap < 1 - 1e-7 for gap in gaps),
        "domain_violations": sum(not lower + 1e-9 < y < upper - 1e-9 for y in ys),
        "inner_segments": len(inner), "aligned_inner_segments": sum(
            abs(positions[v][1] - positions[u][1] + crossing.winding_numbers.get((u, v), 0)
                * period) <= 1e-7 for u, v in inner
        ),
    }


def coordinate_study(graph, run):
    state = run("input", "default", "default", lambda: ({}, prepared(graph)))
    if state is None:
        return
    _, _, sub, paths = state
    crossing = reduce_crossings(sub)
    embedding_crossings = count_crossings(sub, crossing)

    def evaluate(fn, *, geometric=True):
        coords, elapsed = attempt_time(fn)
        metrics = {"algorithm_seconds": elapsed, "embedding_crossings": embedding_crossings,
                   **coordinate_metrics(sub, crossing, coords)}
        if metrics["domain_violations"] or metrics["order_violations"]:
            metrics["status"] = "invalid_coordinates"
        if geometric and metrics.get("status", "ok") == "ok":
            routes, bounds = torus_routes(paths, sub, crossing, coords)
            metrics.update(route_metrics(routes, bounds))
        return metrics, None

    def replicated():
        from torus_layout.coordinates.replicated import expand_3x3
        metrics, value = evaluate(lambda: assign_coordinates(sub, crossing, method="brandes_koepf_3x3"))
        expanded = expand_3x3(sub, crossing)
        metrics["replica_segments_omitted"] = expanded.omitted_segments
        metrics["central_source_segments_omitted"] = sum(
            abs(crossing.winding_numbers.get(edge, 0)) > 1 for edge in sub.graph.edges
        )
        return metrics, value

    for name, fn in (
        ("uniform", lambda: uniform_coordinates(sub, crossing, 0)),
        ("uniform_smooth", lambda: uniform_coordinates(sub, crossing, constants.ALIGNMENT_ITERATIONS)),
        ("bk_no_smooth", lambda: assign_coordinates(sub, crossing, smooth_iterations=0)),
        ("bk", lambda: assign_coordinates(sub, crossing)),
        ("bk_smooth_10", lambda: assign_coordinates(sub, crossing, smooth_iterations=10)),
        ("qp", lambda: assign_coordinates(sub, crossing, method="torus_qp")),
        ("lp", lambda: assign_coordinates(sub, crossing, method="torus_lp")),
        ("lp_bend_1", lambda: assign_coordinates(sub, crossing, method="torus_lp", bend_weight=1)),
    ):
        run("coordinates", name, "bk", lambda: evaluate(fn))
    run("coordinates", "bk_3x3", "bk", replicated)

    def bk_control(assignment):
        return assignment(sub, crossing, smooth_iterations=0)

    for direction in range(4):
        def single():
            with patch.object(coordinate_api, "balanced_coordinates", lambda options: options[direction]):
                return bk_control(assign_coordinates)
        run("bk_merge", f"direction_{direction}", "median", lambda: evaluate(single))
    run("bk_merge", "median", "median", lambda: evaluate(lambda: bk_control(assign_coordinates)))

    def unprojected():
        with patch.object(coordinate_api, "project_all_layers", lambda y, *_: y):
            return bk_control(assign_coordinates)

    run("bk_projection", "off", "on", lambda: evaluate(unprojected, geometric=False))
    run("bk_projection", "on", "on",
        lambda: evaluate(lambda: bk_control(assign_coordinates), geometric=False))

    def unaligned(*, node_order, **_):
        return {node: node for order in node_order.values() for node in order}

    def equal_spacing(node_order, _blocks, min_gap):
        return {node: i * min_gap for order in node_order.values() for i, node in enumerate(order)}

    def replace_bk_step(name, replacement):
        with patch.object(bk, name, replacement):
            return bk_control(assign_coordinates)

    run("bk_components", "all", "all", lambda: evaluate(lambda: bk_control(assign_coordinates)))
    for name, function, replacement in (
        ("no_conflict_marking", "mark_conflicts", lambda **_: set()),
        ("no_alignment", "vertical_alignment", unaligned),
        ("equal_spacing_instead_of_compaction", "horizontal_compaction", equal_spacing),
    ):
        run("bk_components", name, "all", lambda: evaluate(lambda: replace_bk_step(function, replacement)))


def oracle_study(case, run):
    graph = case.graph
    if case.family != "proper":
        def binary():
            result = find_minimum_configuration(graph)
            if result.layer_count is None:
                return {"status": "no_solution"}, None
            pair = (result.layer_count, result.torus_count)
            return {"layers": pair[0], "rank_wrap_edges": pair[1]}, pair

        found = run("search_oracle", "binary", "enumerate", binary)
        binary_certified = found is not None and all(
            record["status"] in (gp.GRB.OPTIMAL, gp.GRB.INFEASIBLE)
            for record in run.outcome["solver"]
        )

        def enumeration():
            candidates = {}
            for layers in range(1, len(graph.nodes) + 1):
                before = len(run.trace)
                try:
                    result = fixed_count(graph, layers)
                except (AttributeError, gp.GurobiError):
                    records = run.trace[before:]
                    if not records or records[-1]["status"] != gp.GRB.TIME_LIMIT:
                        raise
                    result = None
                record = run.trace[-1] if len(run.trace) > before else {}
                record["candidate_layers"] = layers
                status = record.get("status")
                if status == gp.GRB.OPTIMAL and result is not None:
                    candidates[layers] = result[1]
                elif status != gp.GRB.INFEASIBLE:
                    candidates[layers] = None
            if not candidates or None in candidates.values():
                return {"status": "unproven"}, None
            layers = min(candidates, key=lambda layer: (candidates[layer], layer))
            pair = (layers, candidates[layers])
            return {"layers": layers, "rank_wrap_edges": pair[1],
                    "matches_binary": found == pair, "binary_certified": binary_certified}, pair

        run("search_oracle", "enumerate", "enumerate", enumeration)
        return

    width = len(graph.nodes) // 3
    ranks = {u: u // width for u in graph.nodes}
    assignment = LayerAssignmentResult(ranks, {(u, v): ranks[u] > ranks[v] for u, v in graph.edges}, 0)
    sub = insert_dummy_nodes(graph, assignment)
    initial = CrossingResult(base_order(sub.layers, sorted(sub.layers)), dict.fromkeys(graph.edges, 0))

    def evaluate(crossing):
        return crossing_metrics(sub, crossing), crossing

    # Fixed-zero windings turn the objective into inversions within each strip.
    def enumerate_orders():
        layer_ids = sorted(sub.layers)
        by_layer = {layer: [(u, v) for u, v in graph.edges if ranks[u] == layer]
                    for layer in layer_ids}
        independent = float("inf")
        for candidate in product(*(permutations(sub.layers[layer]) for layer in layer_ids)):
            indices = {u: i for layer in candidate for i, u in enumerate(layer)}
            value = sum(
                (indices[u] - indices[a]) * (indices[v] - indices[b]) < 0
                for edges in by_layer.values() for i, (u, v) in enumerate(edges)
                for a, b in edges[i+1:]
            )
            independent = min(independent, value)
        return {"embedding_crossings": independent}, None

    run("sifting_oracle", "enumerate_zero", "enumerate_zero", enumerate_orders)
    run("sifting_oracle", "sift_zero", "enumerate_zero",
        lambda: evaluate(sift(sub, initial, ROUNDS, winding=False)))

    start = initialize(sub, True)
    def exhaustive_seam():
        cost = cut_cost(sub, start)
        layers = sorted(start.order)
        counts = [range(len(start.order[layer])) for layer in layers]
        return {"seam_segments": min(cost(dict(zip(layers, gaps))) for gaps in product(*counts))}, None

    run("seam_oracle", "enumerate_gaps", "enumerate_gaps", exhaustive_seam)
    run("seam_oracle", "dp", "enumerate_gaps", lambda: evaluate(optimize_seam(sub, start)))


def drawing_study(case, run, image_dir):
    if case.family == "fixture":
        regimes = (
            ("plain", 0, 0, (1, 1), (3, 2), 1),
            ("x", 1, 0, (3, 1), (1, 3), 2),
            ("y_positive", 0, 1, (1, 3), (3, 1), 2),
            ("y_negative", 0, -1, (1, 1), (3, 3), 2),
            ("both_corner", 1, 1, (3, 3), (1, 1), 2),
            ("both_multiple", 1, 2, (3, 3), (1, 1), 4),
            ("y_negative_multiple", 0, -2, (1, 1), (3, 3), 3),
        )

        def evaluate(horizontal, vertical, a, b, expected):
            from torus_layout.drawing.models import DrawingData

            edge = (0, 1)
            # Call the artist path used by actual figures to exercise all branches.
            groups = [[] for _ in range(6)]
            group = {(0, 0): 5, (1, 0): 0, (0, 1): 1, (0, -1): 2,
                     (1, 1): 3, (1, -1): 4}[horizontal, (vertical > 0) - (vertical < 0)]
            groups[group].append(edge)
            data = DrawingData([0, 1], {0: a, 1: b}, [0, 1], 2, 1, 0, 4, 0, 4,
                               [], *groups, {edge: vertical})
            calls = []

            def collect(_, start, end, _style, _width, *, arrow, **_kwargs):
                calls.append((start, end, arrow))

            with patch.object(artists, "add_edge_patch", collect):
                artists.draw_edges(None, data, DrawingOptions())
            breaks = sum(
                dist(tuple(x % 4 for x in end), tuple(x % 4 for x in start)) > 1e-7
                for (_, end, _), (start, _, _) in zip(calls, calls[1:])
            )
            length = sum(dist(s, e) for s, e, _ in calls)
            exact = dist(a, (b[0] + 4 * horizontal, b[1] + 4 * vertical))
            error = abs(length - exact)
            valid = (len(calls) == expected and breaks == 0 and error < 1e-7
                     and calls[0][0] == a and dist(calls[-1][1], b) < 1e-7
                     and [arrow for _, _, arrow in calls] == [False] * (expected - 1) + [True])
            return {"piece_count": len(calls), "expected_piece_count": expected,
                    "boundary_breaks": breaks, "length_error": error,
                    "arrow_count": sum(arrow for _, _, arrow in calls),
                    "status": "ok" if valid else "geometry_failed"}, None

        for name, *parameters in regimes:
            run("drawing_geometry", name, name, lambda: evaluate(*parameters))

        def wrapped_route(edge, start, end, *, horizontal=1, vertical=0):
            from torus_layout.drawing.geometry import periodic_edge_segments

            pieces = periodic_edge_segments(
                start, end, x_min=0, x_max=4, y_min=0, y_max=4,
                horizontal_winding=horizontal, vertical_winding=vertical,
            )
            return Route(edge, [start, end], pieces, [])

        def validate_metric(routes, bounds, expected, overlaps=0):
            measured = geometric_crossing_metrics(routes, bounds)
            matches = (measured["geometric_crossings"] == expected
                       and measured["overlapping_edge_pairs"] == overlaps)
            return {**measured, "expected_crossings": expected,
                    "status": "ok" if matches else "geometry_failed"}, None

        first = planar_route((0, 1), [(1, 1), (2, 2), (3, 3)])
        second = planar_route((2, 3), [(1, 3), (3, 1)])
        common_endpoint = planar_route((1, 4), [(3, 3), (3, 1)])
        overlap = planar_route((2, 3), [(1, 1), (3, 3)])
        seam_routes = [wrapped_route((0, 1), (3, 0.5), (1, 1.5)),
                       wrapped_route((2, 3), (3, 1.5), (1, 0.5))]
        near_cut = (1, 4 - 1e-8)
        shared_near_cut = [
            wrapped_route((0, target), near_cut, (2, target), horizontal=0, vertical=1)
            for target in (1, 2)
        ]
        for name, routes, bounds, crossings, overlaps in (
            ("dummy_intersection", [first, second], None, 1, 0),
            ("shared_endpoint", [first, common_endpoint], None, 0, 0),
            ("coincident", [first, overlap], None, 0, 1),
            ("seam_crossing_once", seam_routes, (0, 0, 4, 4), 1, 0),
            ("shared_endpoint_near_cut", shared_near_cut, (0, 0, 4, 4), 0, 0),
        ):
            run("crossing_counter", name, name,
                lambda: validate_metric(routes, bounds, crossings, overlaps))
        return

    result = run("input", "default", "default", lambda: ({}, run_pipeline(case.graph)))
    if result is None:
        return
    image_dir.mkdir(parents=True, exist_ok=True)
    for name, tiles in (("base", False), ("context", True)):
        def render():
            options = DrawingOptions(tile_surroundings=tiles, show_layer_labels=False,
                                     show_legend=False, figsize=(6, 6), dpi=100)
            path = image_dir / f"{case.id}-{name}.png"
            fig, figure_time = attempt_time(
                create_figure, result.subdivided, result.crossing, result.coordinates, options=options
            )
            try:
                _, output_time = attempt_time(
                    output_figure, fig, options=options, save_path=path, show=False
                )
            finally:
                plt.close(fig)
            with Image.open(path) as image:
                width, height = image.size
            return {"figure_seconds": figure_time, "output_seconds": output_time,
                    "image_width_px": width, "image_height_px": height,
                    "image_bytes": path.stat().st_size}, None
        run("render", name, "base", render)
