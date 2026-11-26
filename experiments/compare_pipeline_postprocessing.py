"""Compare the default torus pipeline and sequential radial postprocessing."""
import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from dataclasses import asdict, replace
import json
from pathlib import Path
import signal
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

from compare_global_sifting import (
    ROOT, cases, inner_crossings, write_csv, assignment_metrics, coordinate_metrics,
    record_solver, subdivision_metrics,
)
from torus_layout import pipeline
from torus_layout.crossing import api, sifting
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult, LayerSearchResult, PipelineConfig
from torus_layout.reporting import boundary_metrics
from torus_study.geometry import crossing_metrics, route_metrics, torus_routes

PREVIOUS = ROOT / "output/torus_goal_20261126/matched_split/measurements.csv"
DEFAULT = PipelineConfig()
CONFIGS = {
    "radial": replace(DEFAULT, rounds=5, sifting_method="radial", algo2=True,
                      unwind_levels=True, optimize_seams=True, seam_method="legacy"),
    "global": DEFAULT,
}
BUDGET = 60
SOLVER_SECONDS = 3.0


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_inputs():
    with PREVIOUS.open() as stream:
        previous = list(csv.DictReader(stream))
    expected = {r["case"]: (r["family"], int(r["nodes"]), int(r["edges"])) for r in previous}
    sources = sorted(ROOT.glob("output/**/inputs.jsonl"))
    verified = {}
    for source in sources:
        for line in source.read_text().splitlines():
            row = json.loads(line)
            if row.get("id") in expected and "graph" in row:
                verified.setdefault(row["id"], []).append((source, row["graph"]))
    found = {name: (family, graph) for name, family, graph in cases()}
    assert set(found) == set(expected) and len(expected) == 30
    records = []
    for name, (family, size, arcs) in expected.items():
        actual_family, graph = found[name]
        assert (actual_family, len(graph.nodes), len(graph.edges)) == (family, size, arcs), name
        for source, saved in verified.get(name, []):
            assert set(saved["nodes"]) == set(graph.nodes), (name, source)
            assert set(map(tuple, saved["edges"])) == set(graph.edges), (name, source)
        records.append({"case": name, "family": family, "graph": asdict(graph),
                        "verified_against": [str(source.relative_to(ROOT))
                                             for source, _ in verified.get(name, [])]})
    assert Counter(r["family"] for r in records) == {"ring": 7, "random": 6, "dag": 6, "public": 11}
    return records


class BudgetExceeded(Exception):
    pass


def timeout(*_):
    raise BudgetExceeded(f"post-layering wall time exceeded {BUDGET}s")


def snapshot(order, winding):
    return CrossingResult({k: list(v) for k, v in order.items()}, dict(winding))


def encode_crossing(graph, crossing, paths):
    winding = crossing.winding_numbers
    return {"order": crossing.order, "winding": [[u, v, w] for (u, v), w in winding.items()],
            "crossings": api.count_crossings(graph, crossing),
            "dummy_inner_crossings": inner_crossings(graph, crossing),
            "either_seam_edges": sum(any(graph.torus_flags.get(edge) or winding.get(edge)
                                         for edge in zip(chain, chain[1:])) for chain in paths.values()),
            **boundary_metrics(graph, winding)}


def measure(original, assigned, graph, paths, method):
    attempts, coordinate_calls = [], []
    current = {}
    stage = "sifting"
    snapshot_seconds = 0.0

    def capture(key, order, winding):
        nonlocal snapshot_seconds
        started = perf_counter()
        current[key] = snapshot(order, winding)
        snapshot_seconds += perf_counter() - started

    def reduce(*args, **kwargs):
        nonlocal current, stage
        current = {"settings": kwargs.copy(), "operations": [], "global_rounds": 0,
                   "radial_strip_passes": 0, "radial_strip_counts": {}, "times": {}}
        attempts.append(current)
        stage = "sifting"
        return original_reduce(*args, **kwargs)

    def global_sift(*args, **kwargs):
        def round_end(*_):
            current["global_rounds"] += 1

        result = timed("sifting", original_global, *args, **kwargs, on_round_end=round_end)
        capture("pre", *result)
        return result

    def radial_sift(order, winding, *args, **kwargs):
        timed("sifting", original_radial, order, winding, *args, **kwargs)
        capture("pre", order, winding)

    def strip_pass(fixed, free, *args, **kwargs):
        current["radial_strip_passes"] += 1
        key = f"{fixed}->{free}"
        counts = current["radial_strip_counts"]
        counts[key] = counts.get(key, 0) + 1
        return original_strip(fixed, free, *args, **kwargs)

    def timed(label, fn, *args, **kwargs):
        nonlocal stage
        stage = label
        started = perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            times = current["times"]
            times[label] = times.get(label, 0.0) + perf_counter() - started

    def algo2(*args):
        current["operations"].append({"call": "Algo2"})
        return timed("algo2", original_algo2, *args)

    def boundaries(*args, **kwargs):
        result = timed("boundary", original_boundaries, *args, **kwargs)
        capture("post", result.order, result.winding_numbers)
        stage = "fallback_guard"
        return result

    def observed(name, fn):
        def call(*args, **kwargs):
            current["operations"].append({"call": name, **kwargs})
            return fn(*args, **kwargs)
        return call

    def coordinates(*args, **kwargs):
        nonlocal stage
        stage = "coordinate"
        started = perf_counter()
        call = {"attempt": len(attempts), "status": "ok"}
        coordinate_calls.append(call)
        try:
            return original_coordinates(*args, **kwargs)
        except Exception as error:
            call.update(status=type(error).__name__, error=str(error))
            raise
        finally:
            call["seconds"] = perf_counter() - started

    original_reduce = pipeline.reduce_crossings
    original_global = api.sift_blocks
    original_radial = api.run_radial_sifting
    original_strip = sifting.sift_two_layer_pair
    original_algo2 = api.postprocess_sifting_rotations
    original_boundaries = api._process_boundaries
    original_coordinates = pipeline.assign_coordinates
    hooks = [(pipeline, "assign_layers", lambda *_: assigned),
             (pipeline, "insert_dummy_nodes", lambda *_: graph),
             (pipeline, "reduce_crossings", reduce),
             (pipeline, "assign_coordinates", coordinates),
             (api, "sift_blocks", global_sift),
             (api, "run_radial_sifting", radial_sift),
             (api, "postprocess_sifting_rotations", algo2),
             (api, "_process_boundaries", boundaries),
             (sifting, "sift_two_layer_pair", strip_pass)]
    for name in ("unwind_levels", "optimize_seam", "optimize_joint_seam"):
        hooks.append((api, name, observed(name, getattr(api, name))))

    record = {"status": "ok"}
    result = None
    with ExitStack() as stack:
        for target, name, hook in hooks:
            stack.enter_context(patch.object(target, name, hook))
        old_handler = signal.signal(signal.SIGALRM, timeout)
        started = perf_counter()
        signal.setitimer(signal.ITIMER_REAL, BUDGET)
        try:
            result = pipeline.run_pipeline(original, CONFIGS[method])
        except Exception as error:
            record.update(status="timeout" if isinstance(error, BudgetExceeded) else "error",
                          failure_stage=stage, error_type=type(error).__name__, error=str(error))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            seconds = perf_counter() - started - snapshot_seconds
            signal.signal(signal.SIGALRM, old_handler)

    for attempt in attempts:
        for key in ("pre", "post"):
            if key in attempt:
                attempt[key] = encode_crossing(graph, attempt[key], paths)
    record.update(attempts=attempts, coordinates_attempts=coordinate_calls,
                  fallback=len(attempts) > 1, total_seconds=seconds,
                  coordinate_seconds=sum(c["seconds"] for c in coordinate_calls))
    for key in ("sifting", "algo2", "boundary"):
        record[key + "_seconds"] = sum(a["times"].get(key, 0) for a in attempts)
    if result is not None:
        record["seam_used"] = result.seam_method_used
        try:
            record.update(measure_geometry(original, graph, paths, result.crossing, result.coordinates))
        except Exception as error:
            record.update(status="error", failure_stage="geometry", error_type=type(error).__name__,
                          error=str(error))
    return record



def measure_geometry(original, graph, paths, crossing, coordinates):
    check = coordinate_metrics(graph, crossing, coordinates)
    assert not any(v for k, v in check.items() if k.endswith("violations")), check
    routes, bounds = torus_routes(paths, graph, crossing, coordinates)
    dummy = graph.dummy_nodes
    edges = {edge: edge for edge in graph.graph.edges if set(edge) <= dummy}
    inner_routes, _ = torus_routes(edges, graph, crossing, coordinates)
    geometry = {**route_metrics(routes, bounds), "dummy_inner_geometric_crossings":
                crossing_metrics(inner_routes, bounds)["geometric_crossings"]}
    drawing = {"bounds": bounds, "routes": [asdict(route) for route in routes],
               "nodes": [[node, coordinates.positions[node]] for node in original.nodes]}
    return {"geometry": geometry, "drawing": drawing}


def prepare(original, saved):
    if saved is not None:
        return (LayerSearchResult(**saved["search"]),
                LayerAssignmentResult(dict(saved["layers"]),
                                      {(u, v): flag for u, v, flag in saved["flags"]},
                                      **saved["assignment_metadata"])), saved["solver"]
    solver = []
    with record_solver(SimpleNamespace(local_license=True, solver_seconds=SOLVER_SECONDS), solver):
        return pipeline.assign_layers(original, DEFAULT.balance_method), solver


def run(output, smoke, replay):
    output.mkdir(parents=True, exist_ok=True)
    records = json.loads((replay / "inputs.json").read_text()) if replay else load_inputs()
    write_json(output / "inputs.json", records)
    write_json(output / "settings.json", {"configs": {k: asdict(v) for k, v in CONFIGS.items()},
               "post_layering_budget_seconds": BUDGET, "solver_model_budget_seconds": SOLVER_SECONDS,
               "solver_threads": 1, "solver_seed": 0, "smoke": smoke,
               "previous": str(PREVIOUS.relative_to(ROOT)), "replay": str(replay) if replay else None})
    for i, row in enumerate(records):
        name = row["case"]
        if smoke and name not in ("ws-12-17-ring", "sampson-time-1"):
            continue
        original = Graph(tuple(row["graph"]["nodes"]), tuple(map(tuple, row["graph"]["edges"])))
        shared = None
        try:
            saved = json.loads((replay / f"{name}.json").read_text())["shared"] if replay else None
            assigned, solver = prepare(original, saved)
            if assigned is None:
                raise ValueError("no layer assignment")
            search, assignment = assigned
            assert not assignment_metrics(original, assignment, search.layer_count,
                                          search.torus_count)["assignment_violations"]
            graph = pipeline.insert_dummy_nodes(original, assignment)
            paths, stats = subdivision_metrics(original, graph)
            assert not stats["unit_span_violations"]
            assigned_fields = asdict(assignment)
            del assigned_fields["node_to_layer"], assigned_fields["torus_flags"]
            shared = {"search": asdict(search), "solver": solver,
                      "assignment_metadata": assigned_fields,
                      "layers": list(assignment.node_to_layer.items()),
                      "flags": [[u, v, f] for (u, v), f in assignment.torus_flags.items()],
                      "dummy_nodes": sorted(graph.dummy_nodes),
                      "chains": [[edge, chain] for edge, chain in paths.items()]}
            if saved:
                assert saved["chains"] == json.loads(json.dumps(shared["chains"]))
        except Exception as error:
            outcomes = {m: {"status": "error", "failure_stage": "shared_layering_or_subdivision",
                            "error_type": type(error).__name__, "error": str(error)} for m in CONFIGS}
            order = []
        else:
            order = list(CONFIGS) if i % 2 == 0 else list(reversed(CONFIGS))
            outcomes = {m: measure(original, assigned, graph, paths, m) for m in order}
        write_json(output / f"{name}.json", {**row, "shared": shared, "execution_order": order,
                                            "outcomes": outcomes})
        print(name, {m: (v["status"], v.get("failure_stage"), v.get("seam_used"),
                        round(v.get("total_seconds", 0), 4)) for m, v in outcomes.items()}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--replay", type=Path, help="Reuse saved input and shared layer assignments")
    args = parser.parse_args()
    run(args.output, args.smoke, args.replay)


if __name__ == "__main__":
    main()
