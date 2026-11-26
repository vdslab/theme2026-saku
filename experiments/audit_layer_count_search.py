"""Audit the current binary search with the production fixed-layer model."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
from time import perf_counter
from unittest.mock import patch

import gurobipy as gp
from gurobipy import GRB
import networkx as nx

from torus_layout.layering import minimize_wraps, search
from torus_layout.layering.lib.solver import use_local_license
from torus_study.inputs import generate

SIZES = (20, 40, 60, 80, 100)
SEEDS_BY_FAMILY = {
    "random": tuple(range(701, 706)),
    "scc_chain": tuple(range(701, 706)),
    "watts_strogatz": tuple(range(701, 711)),
}


def write_jsonl(stream, row):
    stream.write(json.dumps(row) + "\n")
    stream.flush()


def evaluate(case, limit, stream, enumeration_size=12):
    nodes = list(case.graph.nodes)
    edges = list(set(case.graph.edges))
    by_phase = defaultdict(list)
    phase = "binary"
    active = {}
    original_optimize = minimize_wraps.optimize

    def optimize(model):
        model.Params.TimeLimit = limit
        model.Params.Threads = 1
        model.Params.Seed = 0
        model.Params.MIPGap = 0
        try:
            original_optimize(model)
        finally:
            active.update(
                variables=model.NumVars, constraints=model.NumConstrs,
                status=model.Status, solutions=model.SolCount,
                solver_seconds=model.Runtime,
            )
            if model.Status in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
                active["bound"] = model.ObjBound

    def solve(v, a, layers, spans=None):
        nonlocal active
        active = {
            "case": case.id, "phase": phase, "call": len(by_phase[phase]) + 1,
            "layers": layers, "wraps": None,
        }
        try:
            result = minimize_wraps.solve_fixed_layers(v, a, layers, spans)
            active["wraps"] = result.torus_count
            status = {GRB.OPTIMAL: "optimal", GRB.INFEASIBLE: "infeasible",
                      GRB.TIME_LIMIT: "time_limit", GRB.SUBOPTIMAL: "suboptimal"}
            active["termination"] = status.get(result.status, "other_status")
            return result
        except gp.GurobiError as exc:
            active["errno"] = exc.errno
            active["termination"] = (
                "license_size" if exc.errno == GRB.Error.SIZE_LIMIT_EXCEEDED
                else "solver_error"
            )
            raise
        finally:
            by_phase[phase].append(active)

    def timed(method, action):
        started = perf_counter()
        layers, wraps = None, None
        try:
            layers, wraps = action()
        except gp.GurobiError:
            pass
        seconds = perf_counter() - started
        calls = by_phase[method]
        return {
            "layers": layers, "wraps": wraps, "seconds": seconds,
            "calls": len(calls), "completed": wraps is not None,
            "terminations": sorted({row["termination"] for row in calls}),
        }

    def binary_action():
        result = search.find_minimum_configuration(case.graph)
        return result.layer_count, result.torus_count

    with (use_local_license(), patch.object(minimize_wraps, "optimize", optimize),
          patch.object(search, "solve_fixed_layers", solve)):
        binary = timed(phase, binary_action)
        phase = "fixed"
        fixed_layers = math.ceil(math.sqrt(2 * len(nodes)))
        fixed = timed(phase, lambda: (fixed_layers, solve(nodes, edges, fixed_layers).torus_count))
        fixed["layers"] = fixed_layers
        layers, wraps = binary["layers"], binary["wraps"]
        if len(nodes) == enumeration_size:
            phase = "enumeration"
            for k in range(1, len(nodes) + 1):
                timed(phase, lambda: (k, solve(nodes, edges, k).torus_count))
            complete = all(r["termination"] in {"optimal", "infeasible"}
                           for r in by_phase[phase])
            optimum = min((r["wraps"], r["layers"]) for r in by_phase[phase]
                          if r["termination"] == "optimal") if complete else None
            verification = {"method": phase, "oracle": optimum,
                            "result": classify(complete and binary["completed"],
                                               optimum == (wraps, layers))}
        else:
            phase = "upper"
            timed(phase, lambda: (len(nodes), solve(nodes, edges, len(nodes)).torus_count))
            upper = by_phase[phase][0]
            phase = "predecessor"
            if layers is not None and layers > 1:
                timed(phase, lambda: (layers - 1, solve(nodes, edges, layers - 1).torus_count))
            previous = by_phase[phase][0] if by_phase[phase] else {}
            upper_checked = binary["completed"] and upper["termination"] == "optimal"
            previous_refutes = (previous.get("wraps") is not None
                                and previous["wraps"] <= wraps)
            bound = previous.get("bound")
            previous_proves = binary["completed"] and (
                layers == 1 or previous.get("termination") == "infeasible"
                or (bound is not None and math.isfinite(bound) and bound > wraps + 1e-6)
            )
            upper_result = classify(upper_checked, wraps == upper["wraps"])
            previous_result = classify(previous_refutes or previous_proves, previous_proves)
            if "mismatch" in (upper_result, previous_result):
                result = "mismatch"
            else:
                result = classify(upper_result == previous_result == "match", True)
            verification = {
                "method": "upper_and_predecessor", "result": result,
                "upper_result": upper_result, "predecessor_result": previous_result,
            }
    for calls in by_phase.values():
        for row in calls:
            if "bound" in row and not math.isfinite(row["bound"]):
                row["bound"] = None
            write_jsonl(stream, row)
    return {"case": case.id, "nodes": len(nodes), "edges": len(edges),
            "family": case.family, "seed": case.seed, "binary": binary,
            "fixed": fixed, "verification": verification}


def classify(checked, matches):
    if checked:
        return "match" if matches else "mismatch"
    return "unverified"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--time-limit", type=float, default=1)
    parser.add_argument("--sizes", type=int, nargs="+", default=SIZES)
    args = parser.parse_args()
    if min(args.sizes) < 5 or len(set(args.sizes)) != len(args.sizes):
        parser.error("--sizes requires distinct sizes of at least 5")
    args.output.mkdir(parents=True, exist_ok=False)
    settings = {
        "sizes": args.sizes, "seeds_by_family": SEEDS_BY_FAMILY,
        "families": list(SEEDS_BY_FAMILY), "edges_per_node": 2,
        "time_limit_seconds_per_call": args.time_limit, "threads": 1, "solver_seed": 0,
        "mip_gap": 0, "license": "local", "parallel_cases": 1,
        "python": platform.python_version(), "platform": platform.platform(),
        "gurobi": gp.gurobi.version(), "networkx": nx.__version__,
        "source_sha256": {
            str(path): sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path("experiments/torus_study/inputs.py"),
                         *Path("src/torus_layout/layering").glob("*.py"),
                         *Path("src/torus_layout/layering/lib").glob("*.py"))
        },
    }
    (args.output / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    with ((args.output / "inputs.jsonl").open("w") as inputs,
          (args.output / "calls.jsonl").open("w") as calls,
          (args.output / "results.jsonl").open("w") as results):
        cases = ((n, family, seed) for n in args.sizes
                 for family, seeds in SEEDS_BY_FAMILY.items() for seed in seeds)
        for n, family, seed in cases:
            case = generate(family, n, 2, seed)
            write_jsonl(inputs, case.manifest())
            row = evaluate(case, args.time_limit, calls, min(args.sizes))
            write_jsonl(results, row)
            print(case.id, row["verification"]["result"], flush=True)


if __name__ == "__main__":
    main()
