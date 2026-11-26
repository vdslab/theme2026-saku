"""Compare global sifting block visit schedules using a serial paired experiment."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import signal
from time import perf_counter
from types import SimpleNamespace

import gurobipy as gp

from old_torus_layout.lib.generate_torus_graph import generate_watts_strogatz_graph
from torus_layout.coordinates import assign_coordinates
from torus_layout.coordinates.blocks import UnsplitBlockOrderError
from torus_layout.crossing.api import _process_boundaries, count_crossings, reduce_crossings
from torus_layout.crossing.global_sifting import sift_blocks
from torus_layout.crossing.initialization import initial_orders
from torus_layout.crossing.seam import seam_score
from torus_layout.layering.router import assign_layers
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult, PipelineConfig
from torus_layout.subdivision import build_dummy_blocks, insert_dummy_nodes
from torus_study.geometry import route_metrics, torus_routes
from torus_study.inputs import generate
from torus_study.stages import assignment_metrics, chains_for, record_solver

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/global_block_order_20261126"
SIZES = (20, 40, 60, 80, 100)
FAMILIES = {"random": 5, "scc_chain": 5, "watts_strogatz": 10}
METHODS = ("forward", "alternating")
MODES = ("fixed", "early")
ROUNDS = 5
CONFIG = PipelineConfig()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False) + "\n")
    temp.replace(path)


def inputs():
    # Match prior WS pair-sweep parameters. Reuse exact saved graphs where available.
    old_ws = ROOT / "experiments/results/torus_sweep_direction/ws100/embeddings.jsonl"
    ws = {}
    if old_ws.exists():
        for line in old_ws.read_text().splitlines():
            entry = json.loads(line)
            ws[entry["nodes"], entry["seed"]] = entry
    manifests = {}
    for folder in ("crossing", "scaling"):
        path = ROOT / f"output/torus_experiment_20261120/{folder}/inputs.jsonl"
        if path.exists():
            for line in path.read_text().splitlines():
                entry = json.loads(line)
                manifests.setdefault(entry["id"], (entry["graph"], str(path.relative_to(ROOT))))
    cases = []
    for n in SIZES:
        for family, count in FAMILIES.items():
            for seed in range(count):
                key = f"{family}-{n}-2-{seed}"
                if family == "watts_strogatz":
                    if (n, seed) in ws:
                        entry = ws[n, seed]
                        vertices, edges = entry["vertices"], entry["original_edges"]
                        source = str(old_ws.relative_to(ROOT))
                    else:
                        vertices, edges = generate_watts_strogatz_graph(
                            n, k=4, p=0.8, seed=seed, ensure_connected=True,
                        )
                        edges = sorted(set(edges))
                        source = "evaluate_torus_sweep_ws100.py parameters"
                    graph = dict(nodes=vertices, edges=edges)
                elif key in manifests:
                    graph, source = manifests[key]
                else:
                    generated = generate(family, n, 2, seed).graph
                    graph = dict(nodes=generated.nodes, edges=generated.edges)
                    source = "torus_study.inputs.generate"
                cases.append(dict(id=key, n=n, family=family, seed=seed, graph=graph, source=source))
    return cases


def original(case):
    return Graph(tuple(case["graph"]["nodes"]), tuple(map(tuple, case["graph"]["edges"])))


def pack(order, winding):
    return dict(order=list(order.items()), winding=list(winding.items()))


def unpack(embedding):
    return CrossingResult(dict(embedding["order"]),
                          {tuple(edge): value for edge, value in embedding["winding"]})


def prepare(graph, solver_seconds):
    trace = []
    settings = SimpleNamespace(local_license=True, solver_seconds=solver_seconds)
    try:
        with record_solver(settings, trace):
            result = assign_layers(graph, CONFIG.balance_method)
    except gp.GurobiError as error:
        status = ("license_limit" if error.errno == gp.GRB.Error.SIZE_LIMIT_EXCEEDED
                  else "solver_error")
        return dict(status=status, errno=error.errno, solver=trace,
                    error=str(error) if status == "license_limit" else type(error).__name__)
    if result is None:
        status = "layer_timeout" if any(m["status"] == gp.GRB.TIME_LIMIT for m in trace) else "no_assignment"
        return dict(status=status, solver=trace)
    search, assigned = result
    validation = assignment_metrics(graph, assigned, search.layer_count, search.torus_count)
    if validation["assignment_violations"]:
        return dict(status="invalid_assignment", solver=trace, validation=validation)
    sub = insert_dummy_nodes(graph, assigned)
    order = initial_orders(sub.layers, sorted(sub.layers), list(sub.graph.edges))[0]
    # The legacy algorithm projects this order to a shared block list before round 1.
    return dict(status="ok", solver=trace, layers=list(assigned.node_to_layer.items()),
                torus_flags=list(assigned.torus_flags.items()),
                proper_edges=sub.graph.edges, proper_layers=list(sub.layers.items()),
                segment_counts=sub.segment_counts, initial=pack(order, dict.fromkeys(sub.graph.edges, 0)))


def subdivided(graph, prep):
    assigned = LayerAssignmentResult(dict(prep["layers"]),
                                     {tuple(edge): value for edge, value in prep["torus_flags"]}, 0)
    sub = insert_dummy_nodes(graph, assigned)
    assert sub.graph.edges == tuple(map(tuple, prep["proper_edges"]))
    assert sub.layers == dict(prep["proper_layers"])
    assert sub.segment_counts == tuple(prep["segment_counts"])
    return sub


class SiftingTimeout(Exception):
    pass


def timeout(signum, frame):
    raise SiftingTimeout


def timed_sift(sub, start, layers, options, seconds):
    handler = signal.signal(signal.SIGALRM, timeout)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        started = perf_counter()
        order, winding = sift_blocks(sub, start, layers, ROUNDS, **options)
        return perf_counter() - started, pack(order, winding)
    except SiftingTimeout:
        return perf_counter() - started, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)


def traced_sift(sub, start, layers, options, seconds):
    trace, visits = [], []
    candidates = 0

    def begin(sequence, order, winding):
        if not trace:
            trace.append(dict(round=0, crossings=count_crossings(sub, CrossingResult(order, winding)),
                              **pack(deepcopy(order), winding.copy())))
        visits.append(sequence)

    def end(order, winding):
        trace.append(dict(round=len(trace), crossings=count_crossings(sub, CrossingResult(order, winding)),
                          visits=len(visits[-1]), candidates=candidates -
                          sum(row.get("candidates", 0) for row in trace)))

    def candidate():
        nonlocal candidates
        candidates += 1

    started = perf_counter()
    stop = None if seconds is None else lambda: perf_counter() - started >= seconds
    order, winding = sift_blocks(sub, start, layers, ROUNDS, **options, should_stop=stop,
                                 on_round_start=begin, on_round_end=end, on_candidate=candidate)
    return pack(order, winding), trace, visits, candidates


def finish(sub, chains, embedding):
    start = unpack(embedding)

    def boundary(method):
        return _process_boundaries(
            sub, start, CONFIG.unwind_levels, CONFIG.optimize_seams, True, seam_method=method,
        )

    def coordinates(crossing):
        return assign_coordinates(sub, crossing, method=CONFIG.coordinate_method,
                                  bend_weight=CONFIG.coordinate_bend_weight)

    method = CONFIG.seam_method
    fallback = False
    try:
        crossing = boundary(method)
    except (ValueError, RuntimeError) as error:
        return dict(status="boundary_error", fallback=fallback, error=str(error))
    stage = "coordinate_error"
    try:
        try:
            position = coordinates(crossing)
        except UnsplitBlockOrderError as error:
            fallback = True
            method = "legacy"
            stage = "fallback_boundary_error"
            crossing = boundary(method)
            if seam_score(sub, crossing, True)[0] != 0:
                raise error
            stage = "coordinate_error"
            position = coordinates(crossing)
        stage = "geometry_error"
        routes, bounds = torus_routes(chains, sub, crossing, position)
        geometry = route_metrics(routes, bounds)
    except (ValueError, RuntimeError, AssertionError) as error:
        return dict(status=stage, method=method, fallback=fallback, error=str(error))
    return dict(status="ok", method=method, fallback=fallback, **geometry,
                crossing=pack(crossing.order, crossing.winding_numbers),
                positions=list(position.positions.items()), period=position.period)


def check_pilot(sub, start, baseline_path):
    layers = sorted(sub.layers)
    runs = [
        traced_sift(deepcopy(sub), deepcopy(start), layers, dict(alternate_visits=alt, early_exit=False), None)
        for alt in (False, True)
    ]
    one = [pack(*sift_blocks(deepcopy(sub), deepcopy(start), layers, 1, alternate_visits=alt))
           for alt in (False, True)]
    assert runs[0][2][0] == runs[1][2][0]
    assert one[0] == one[1]
    assert runs[0][1][1] == runs[1][1][1]
    early = dict(alternate_visits=False, early_exit=True)
    explicit = traced_sift(deepcopy(sub), deepcopy(start), layers, early, None)[0]
    baseline = sift_blocks
    if baseline_path:
        spec = importlib.util.spec_from_file_location(
            "torus_layout.crossing._block_order_baseline", baseline_path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        baseline = module.sift_blocks
    assert explicit == pack(*baseline(deepcopy(sub), deepcopy(start), layers, ROUNDS))
    expected = reduce_crossings(sub, sifting_method="global", unwind=False, optimize_seams=False, algo2=False)
    assert explicit == pack(expected.order, expected.winding_numbers)
    return dict(first_visit=runs[0][2][0], first_state=one[0],
                early_forward_matches_default=True, checked_prechange_source=bool(baseline_path),
                prechange_sha256=(hashlib.sha256(baseline_path.read_bytes()).hexdigest()
                                  if baseline_path else None))


def evaluate(graph, prep, index, limits, executor):
    sub = subdivided(graph, prep)
    start = unpack(prep["initial"]).order
    layers = sorted(sub.layers)
    blocks = len(build_dummy_blocks(sub))
    chains = chains_for(graph, sub)
    rows = []
    execution = METHODS if index % 2 == 0 else METHODS[::-1]
    measured_runs = []
    for mode in MODES:
        for method in execution:
            options = dict(alternate_visits=method == "alternating", early_exit=mode == "early")
            seconds, measured = timed_sift(deepcopy(sub), deepcopy(start), layers, options, limits)
            measured_runs.append((mode, method, options, seconds, measured))
            print(f"  {mode} {method}: {seconds:.3f}s"
                  + (" (timeout)" if measured is None else ""), flush=True)
    # Keep all trace workers idle while measuring. Their output is consumed
    # before the next input's measured runs begin.
    jobs = {}
    if executor is not None:
        for mode, method, options, _, measured in measured_runs:
            if measured is not None:
                jobs[mode, method] = executor.submit(
                    traced_sift, deepcopy(sub), deepcopy(start), layers, options, None,
                )
    for mode, method, options, seconds, measured in measured_runs:
        if measured is None:
            rows.append(dict(mode=mode, method=method, seconds=seconds, status="sifting_timeout"))
            continue
        if executor is None:
            result, trace, visits, candidates = traced_sift(
                deepcopy(sub), deepcopy(start), layers, options, None,
            )
        else:
            result, trace, visits, candidates = jobs[mode, method].result()
        assert measured == result
        assert all(len(v) == len(set(v)) == blocks for v in visits)
        assert len(trace) == len(visits) + 1
        if mode == "fixed":
            assert len(visits) == ROUNDS
        rows.append(dict(mode=mode, method=method, seconds=seconds, status="ok",
                         rounds=len(visits), visits=sum(map(len, visits)), candidates=candidates,
                         visits_by_round=visits, trace=trace, final=result,
                         crossings=trace[-1]["crossings"], drawing=finish(sub, chains, result)))
    return rows


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    (output / "cases").mkdir(exist_ok=True)
    (output / "prepared").mkdir(exist_ok=True)
    manifest = output / "inputs.json"
    if not manifest.exists():
        write(manifest, inputs())
    cases = read(manifest)
    settings = dict(rounds=ROUNDS, solver_seconds_per_model=args.solver_seconds,
                    sifting_seconds_per_run=args.sifting_seconds, solver_threads=1, solver_seed=0,
                    license="local", pipeline=vars(CONFIG), python=platform.python_version(),
                    gurobi=gp.__version__, platform=platform.platform(),
                    sifting_sha256=hashlib.sha256(Path(sift_blocks.__code__.co_filename).read_bytes()).hexdigest())
    settings_path = output / "settings.json"
    if settings_path.exists() and read(settings_path) != settings:
        raise ValueError("Existing settings differ; use a fresh output directory.")
    write(settings_path, settings)
    for index, case in enumerate(cases):
        path = output / "cases" / f"{case['id']}.json"
        retry_seconds = None
        if path.exists():
            previous = read(path)
            if (previous["prep_status"] != "layer_timeout" or args.retry_layer_seconds is None
                    or previous.get("layer_retry_seconds") == args.retry_layer_seconds):
                continue
            retry_seconds = args.retry_layer_seconds
        print(f"{index + 1}/{len(cases)} {case['id']}", flush=True)
        graph = original(case)
        prep_path = output / "prepared" / path.name
        if not prep_path.exists():
            write(prep_path, prepare(graph, args.solver_seconds))
        prep = read(prep_path)
        if retry_seconds is not None and prep.get("layer_retry_seconds") != retry_seconds:
            updated = prepare(graph, retry_seconds)
            updated.update(layer_retry_seconds=retry_seconds, previous_attempt=prep)
            write(prep_path, updated)
            prep = read(prep_path)
        rows = []
        if prep["status"] == "ok":
            if not (output / "pilot.json").exists():
                sub = subdivided(graph, prep)
                pilot = check_pilot(sub, unpack(prep["initial"]).order, args.baseline)
                write(output / "pilot.json", dict(case=case["id"], **pilot))
                print("  Pilot checks passed", flush=True)
            manager = (ProcessPoolExecutor(max_workers=args.trace_workers)
                       if args.trace_workers > 1 else nullcontext())
            with manager as executor:
                rows = evaluate(graph, prep, index, args.sifting_seconds, executor)
        print(f"  preparation={prep['status']}", flush=True)
        write(path, dict(case=case["id"], prep_status=prep["status"],
                         trace_workers=args.trace_workers, layer_retry_seconds=retry_seconds,
                         trials=rows))
        if args.pilot_only and rows:
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--solver-seconds", type=float, default=1.0)
    parser.add_argument("--sifting-seconds", type=float, default=30.0)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--trace-workers", type=int, choices=range(1, 5), default=1,
                        help="Parallel counting replays per input; timing is always serial")
    parser.add_argument("--retry-layer-seconds", type=float,
                        help="Retry previously timed-out layer assignments at this per-model limit")
    args = parser.parse_args()
    if min(args.solver_seconds, args.sifting_seconds) <= 0:
        parser.error("Time limits must be positive")
    if args.retry_layer_seconds is not None and args.retry_layer_seconds <= args.solver_seconds:
        parser.error("The retry limit must exceed the initial solver limit")
    run(args)
