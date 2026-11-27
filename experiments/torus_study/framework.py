"""End-to-end layout comparisons through a shared centerline evaluator."""

from collections import Counter
from contextlib import ExitStack
from functools import wraps
import json
from math import atan, hypot, radians, tau
from pathlib import Path
import resource
import subprocess
import sys
from unittest.mock import patch

from torus_layout import pipeline
from torus_layout.layering import router
from torus_layout.models import PipelineConfig
from layout_common.cycle_removal import remove_cycles
from layout_common.hierarchy import insert_dummy_nodes
from sugiyama_layout import condense_cycles
from sugiyama_layout import coordinate_assignment as planar_coordinates
from sugiyama_layout import crossing_reduction as planar_crossing
from sugiyama_layout.layer_assignment import assign_layers
from radial_layout import coordinate_assignment as radial_coordinates
from radial_layout import crossing_reduction as radial_crossing
from radial_layout.layer_assignment import assign_layers as assign_radial_layers
from radial_layout.drawing import _sample_chain, _sampling_steps

from .geometry import crossing_metrics, planar_route, route_metrics, torus_routes
from .stages import assignment_metrics, attempt_time, initialize, sift, subdivision_metrics


def measured_torus(graph, config=None):
    timings = {}

    def timed(owner, name):
        function = getattr(owner, name)

        @wraps(function)
        def wrapper(*args, **kwargs):
            result, elapsed = attempt_time(function, *args, **kwargs)
            timings[f"{name}_seconds"] = elapsed
            return result

        return patch.object(owner, name, wrapper)

    with ExitStack() as stack:
        for name in ("assign_layers", "insert_dummy_nodes", "reduce_crossings", "assign_coordinates"):
            stack.enter_context(timed(pipeline, name))
        for name in ("find_minimum_configuration", "balance_layers"):
            stack.enter_context(timed(router, name))
        result, elapsed = attempt_time(pipeline.run_pipeline, graph, config)
    return result, {**timings, "layout_seconds": elapsed}


def torus(graph, config=None, *, scaling=False):
    result, metrics = measured_torus(graph, config)
    if result is None:
        return {**metrics, "status": "no_solution"}, None
    # The pipeline includes both attempts when it falls back to the legacy cut.
    metrics.update(
        reduce_crossings_seconds=result.crossing_time,
        assign_coordinates_seconds=result.coordinate_time,
        seam_method_used=result.seam_method_used,
    )
    metrics.update(assignment_metrics(graph, result.assignment, result.search.layer_count,
                                      result.search.torus_count))
    paths, subs = subdivision_metrics(graph, result.subdivided)
    metrics.update(subs)
    if metrics["assignment_violations"] or metrics["unit_span_violations"]:
        return {**metrics, "status": "invalid_layout"}, None
    if scaling:
        return metrics, result
    routes, bounds = torus_routes(paths, result.subdivided, result.crossing, result.coordinates)
    metrics["reverse_direction_edges"] = sum(
        any(b[0] < a[0] for a, b in zip(route.points, route.points[1:])) for route in routes
    )
    return {**metrics, **completed_metrics(routes, bounds)}, (routes, bounds)


def completed_metrics(routes, bounds=None, *, bends=True, geometry=True):
    metrics = route_metrics(routes, bounds, bends=bends, geometry=geometry)
    if bounds is None:
        width, height = metrics["centerline_bbox_width"], metrics["centerline_bbox_height"]
    else:
        width, height = bounds[2:]
    diagonal = hypot(width, height)
    if diagonal > 0:
        metrics["length_per_frame_diagonal"] = metrics["total_edge_length"] / diagonal
        metrics["max_length_per_frame_diagonal"] = metrics["max_edge_length"] / diagonal
        metrics["frame_aspect"] = width / height if height > 0 else None
    return metrics


def radial_drawing_metrics(centerlines, multiplicities, chains, coordinates):
    metrics = crossing_metrics(centerlines.values(), None, multiplicities=multiplicities)
    bends = 0
    max_bends = 0
    max_span = 0.0
    for edge, chain in chains.items():
        previous_tangent = None
        edge_bends = 0
        for u, v in zip(chain, chain[1:]):
            inner, start = coordinates.polar[u]
            outer, end = coordinates.polar[v]
            span = end - start + tau * coordinates.winding[u, v] if inner else 0.0
            # Tangent angles relative to the outward radial direction at
            # either end, from the derivative of the spiral in Eq. (4).
            slope = span / (outer - inner)
            if previous_tangent is not None and abs(atan(inner * slope) - previous_tangent) > radians(1):
                edge_bends += 1
            previous_tangent = atan(outer * slope)
            max_span = max(max_span, abs(span) / tau)
        bends += edge_bends * multiplicities[edge]
        max_bends = max(max_bends, edge_bends)
    return {**metrics, "bends": bends, "max_bends_per_edge": max_bends, "max_segment_turns": max_span}


def repository_baseline(graph, radial=False, *, condense=False):
    def layout():
        prepare = condense_cycles if condense else remove_cycles
        acyclic = prepare(graph.nodes, graph.edges)
        layout_edges = tuple(dict.fromkeys(acyclic.edges))
        layer_assignment = assign_radial_layers if radial else assign_layers
        ranks = layer_assignment(acyclic.nodes, layout_edges)
        proper = insert_dummy_nodes(acyclic.nodes, layout_edges, ranks)
        if radial:
            embedding = radial_crossing.reduce_crossings(proper.layers, proper.edges)
            positions = radial_coordinates.assign_coordinates(embedding)
        else:
            embedding = planar_crossing.reduce_crossings(proper.layers, proper.edges)
            positions = planar_coordinates.assign_coordinates(
                embedding, proper.edges, dummy_nodes=proper.dummy_nodes
            )
        return acyclic, layout_edges, proper, embedding, positions

    (acyclic, layout_edges, proper, embedding, positions), elapsed = attempt_time(layout)
    metrics = {}
    centerlines = {}
    multiplicities = Counter()
    if radial:
        sampling_steps = _sampling_steps(positions.polar, positions.winding)
        centerlines = {
            edge: planar_route(edge, _sample_chain(chain, positions.polar, positions.winding, sampling_steps))
            for edge, chain in proper.chains.items()
        }
    routes = []
    for edge in acyclic.edges if condense else graph.edges:
        reverse = edge in acyclic.reversed_edges
        layout_edge = edge[::-1] if reverse else edge
        if radial:
            multiplicities[layout_edge] += 1
            points = centerlines[layout_edge].points
        else:
            points = [positions[u] for u in proper.chains[layout_edge]]
        routes.append(planar_route(edge, points[::-1] if reverse else points))
    if radial:
        metrics = radial_drawing_metrics(centerlines, multiplicities, proper.chains, positions)
    return {
        "reference_method": "bachmaier_2007_sifting" if radial else "sugiyama_1981_bc_pr",
        "cycle_preprocessing": "scc_condensation" if condense else "eades_lin_smyth",
        "layout_input_nodes": len(acyclic.nodes),
        "layout_input_edges": len(layout_edges),
        "combinatorial_crossings": (embedding.crossings if radial
                                    else planar_crossing.count_crossings(embedding, proper.edges)),
        "layout_seconds": elapsed, "layers": len(proper.layers),
        "dummy_nodes": len(proper.dummy_nodes), "proper_edges": len(proper.edges),
        "reverse_direction_edges": len(acyclic.reversed_edges),
        **completed_metrics(routes, bends=not radial, geometry=not radial),
        **metrics,
    }, (routes, None)


GRAPHVIZ_OPTIONS = {
    "dot": ("-Grankdir=LR",),
    "twopi": (),
    "circo": (),
    "sfdp": ("-Gstart=42", "-Goverlap=prism"),
}


def graphviz(graph, executable, timeout, *, engine="dot", measure_geometry=True):
    flags = (f"-K{engine}", "-Gsplines=polyline", *GRAPHVIZ_OPTIONS[engine], "-Tjson")
    ids = {node: f"n{index}" for index, node in enumerate(graph.nodes)}
    labels = {label: node for node, label in ids.items()}
    source = "digraph {\n"
    source += "".join(f"{ids[u]};\n" for u in graph.nodes)
    source += "".join(f"{ids[u]} -> {ids[v]};\n" for u, v in graph.edges) + "}\n"
    proc, elapsed = attempt_time(
        subprocess.run, [executable, *flags], input=source, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=True,
    )
    parsed = json.loads(proc.stdout)
    nodes = {obj["_gvid"]: (labels[obj["name"]], tuple(map(float, obj["pos"].split(","))))
             for obj in parsed.get("objects", [])}
    if {label for label, _ in nodes.values()} != set(graph.nodes):
        raise ValueError("Graphviz changed vertex set")
    routes = []
    reverse, same_rank = 0, 0
    for edge in parsed.get("edges", []):
        u, start = nodes[edge["tail"]]
        v, end = nodes[edge["head"]]
        reverse += end[0] < start[0]
        same_rank += end[0] == start[0]
        commands = [op for op in edge["_draw_"] if op["op"] in ("b", "B", "L")]
        if not commands:
            raise ValueError("missing Graphviz centerline")
        points = [start]
        corners = [start]
        for command in commands:
            control = [tuple(point) for point in command["points"]]
            if command["op"] == "L":
                points.extend(control)
                corners.extend(control)
                continue
            if (len(control) - 1) % 3:
                raise ValueError("unexpected Graphviz spline encoding")
            points.append(control[0])
            corners.extend(control[::3])
            for i in range(0, len(control) - 1, 3):
                a, b, c, d = control[i:i+4]
                for step in range(1, 17):
                    t = step / 16
                    s = 1 - t
                    points.append(tuple(s**3*w + 3*s*s*t*x + 3*s*t*t*y + t**3*z
                                        for w, x, y, z in zip(a, b, c, d)))
        points.append(end)
        corners.append(end)
        routes.append(planar_route((u, v), points, corners))
    if Counter(route.edge for route in routes) != Counter(graph.edges):
        raise ValueError("Graphviz changed edge set")
    direction = {}
    if engine == "dot":
        direction = {"reverse_direction_edges": reverse, "same_rank_edges": same_rank}
    metrics = {"layout_seconds": elapsed, "tool": "graphviz", "engine": engine,
               "tool_options": " ".join(flags), **direction}
    if measure_geometry:
        metrics.update(completed_metrics(routes))
    return metrics, (routes, None)


def elk_layered(graph, node_executable, package_dir, timeout):
    ids = {node: f"n{index}" for index, node in enumerate(graph.nodes)}
    options = {"elk.algorithm": "layered", "elk.direction": "RIGHT",
               "elk.edgeRouting": "POLYLINE", "elk.layered.layering.strategy": "NETWORK_SIMPLEX"}
    payload = {
        "id": "graph",
        "layoutOptions": options,
        "children": [{"id": label, "width": 54, "height": 36} for label in ids.values()],
        "edges": [{"id": f"e{i}", "sources": [ids[u]], "targets": [ids[v]]}
                  for i, (u, v) in enumerate(graph.edges)],
    }
    bridge = Path(__file__).with_name("elk_layout.cjs")
    proc, elapsed = attempt_time(
        subprocess.run, [node_executable, str(bridge), package_dir],
        input=json.dumps(payload), encoding="utf-8", stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=True,
    )
    layout = json.loads(proc.stdout)
    positions = {item["id"]: (item["x"] + item["width"] / 2, -(item["y"] + item["height"] / 2))
                 for item in layout.get("children", [])}
    if positions.keys() != set(ids.values()):
        raise ValueError("ELK changed vertex set")
    edges = {item["id"]: item for item in layout.get("edges", [])}
    if edges.keys() != {item["id"] for item in payload["edges"]}:
        raise ValueError("ELK changed edge set")
    routes = []
    reverse = same_rank = 0
    for i, (u, v) in enumerate(graph.edges):
        edge = edges[f"e{i}"]
        if edge["sources"] != [ids[u]] or edge["targets"] != [ids[v]]:
            raise ValueError("ELK changed edge endpoints")
        section, = edge["sections"]
        points = [section["startPoint"], *section.get("bendPoints", []), section["endPoint"]]
        start, end = positions[ids[u]], positions[ids[v]]
        reverse += end[0] < start[0]
        same_rank += end[0] == start[0]
        routes.append(planar_route((u, v), [start, *((p["x"], -p["y"]) for p in points), end]))
    return {"layout_seconds": elapsed, "tool": "elkjs", "engine": "layered",
            "tool_options": json.dumps(options, sort_keys=True),
            "reverse_direction_edges": reverse, "same_rank_edges": same_rank,
            **completed_metrics(routes)}, (routes, None)


def framework_study(graph, run, args):
    config = PipelineConfig(optimize_seams=False, unwind_levels=False)

    def cylindrical_reference():
        def fixed_winding(subdivided, rounds, **_kwargs):
            initial = initialize(subdivided, True)
            initial.winding_numbers.update(dict.fromkeys(subdivided.graph.edges, 0))
            return sift(subdivided, initial, rounds, winding=False)

        with patch.object(pipeline, "reduce_crossings", fixed_winding):
            return torus(graph, config)

    variants = {
        "torus": lambda: torus(graph),
        "sugiyama": lambda: repository_baseline(graph),
        "radial": lambda: repository_baseline(graph, radial=True),
        "sugiyama_1981": lambda: repository_baseline(graph, condense=True),
        "dot": lambda: graphviz(graph, args.dot, args.comparison_seconds),
        "torus_without_unwind_or_dp": lambda: torus(graph, config),
        "cylindrical_reference": cylindrical_reference,
    }
    if args.variant in ("twopi", "circo", "sfdp"):
        evaluate = lambda: graphviz(graph, args.graphviz, args.comparison_seconds, engine=args.variant)
    elif args.variant == "elk":
        evaluate = lambda: elk_layered(graph, args.node, args.elkjs, args.comparison_seconds)
    else:
        evaluate = variants[args.variant]
    def with_memory():
        metrics, layout = evaluate()
        # Each framework variant gets a fresh worker. External tools run in its child.
        return {
            **metrics,
            "peak_worker_mib": peak_mib(resource.RUSAGE_SELF),
            "peak_child_mib": peak_mib(resource.RUSAGE_CHILDREN),
        }, layout

    run("framework", args.variant, args.baseline, with_memory)


def peak_mib(who):
    rss = resource.getrusage(who).ru_maxrss
    return rss / (1024**2 if sys.platform == "darwin" else 1024)


def scaling_study(graph, run):
    def evaluate():
        metrics, layout = torus(graph, scaling=True)
        metrics["peak_process_mib"] = peak_mib(resource.RUSAGE_SELF)
        return metrics, layout
    run("scaling", "torus", "torus", evaluate)
