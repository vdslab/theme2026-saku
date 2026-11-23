"""Check the 3×3 BK period confound and local solver model-size limits."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

from run_torus_study import ROOT, write_csv

sys.path.insert(0, str(ROOT / "src"))

import gurobipy as gp

from torus_layout.coordinates import api
from torus_layout.crossing import count_seam_segments, optimize_seam, reduce_crossings, unwind_levels
from torus_layout.layering.lib.solver import create_gurobi_env, use_local_license
from torus_layout.models import Graph

from torus_study.geometry import route_metrics, torus_routes
from torus_study.stages import coordinate_metrics, prepared, record_solver


def graph_cases(manifest):
    for line in manifest.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["seed"] != 0:
            continue
        common = {"case": item["id"], "family": item["family"], "nodes": item["nodes"],
                  "edges": item["edges"], "seed": item["seed"]}
        data = item["graph"]
        yield common, Graph(tuple(data["nodes"]), tuple(map(tuple, data["edges"])))


def fixed_period_cases(manifest, solver_seconds):
    for common, graph in graph_cases(manifest):
        solves = []
        with record_solver(SimpleNamespace(local_license=True, solver_seconds=solver_seconds), solves):
            try:
                _, _, sub, paths = prepared(graph)
                crossing = reduce_crossings(sub)
                left = api.assign_coordinates(sub, crossing, method="brandes_koepf")
                right = api.assign_coordinates(sub, crossing, method="brandes_koepf_3x3")
                with patch.object(api, "drawing_period", return_value=right.period):
                    common_period = api.assign_coordinates(sub, crossing, method="brandes_koepf")
            except (ValueError, AttributeError, RuntimeError, gp.GurobiError) as exc:
                yield {**common, "variant": "input", "status": type(exc).__name__,
                       "solver_errno": getattr(exc, "errno", None)}
                continue
        model_statuses = dict(Counter(s["status"] for s in solves))
        for name, coords in (("default_bk", left), ("same_period_bk", common_period), ("bk_3x3", right)):
            metrics = coordinate_metrics(sub, crossing, coords)
            route, bounds = torus_routes(paths, sub, crossing, coords)
            yield {**common, "variant": name, "status": "ok",
                   "solve_status_counts": json.dumps(model_statuses, sort_keys=True),
                   **metrics, **route_metrics(route, bounds)}


def guarded_seams(manifest, solver_seconds):
    for common, graph in graph_cases(manifest):
        solves = []
        with record_solver(SimpleNamespace(local_license=True, solver_seconds=solver_seconds), solves):
            try:
                _, _, sub, paths = prepared(graph)
                rotated = reduce_crossings(sub, unwind=False, optimize_seams=False, algo2=True)
                dp_only = optimize_seam(sub, rotated)
                early = unwind_levels(sub, rotated)
                first = optimize_seam(sub, early)
                inner = unwind_levels(sub, rotated, include_non_inner=False)
                cut_first = first if inner == early else optimize_seam(sub, inner)
                unwind_late = unwind_levels(sub, cut_first)
                second = optimize_seam(sub, unwind_late) if unwind_late != cut_first else cut_first

                def seam_count(candidate):
                    return count_seam_segments(sub, candidate)

                current = min((first, second), key=seam_count)
                # The supplement adds the no-UNWIND DP candidate to the existing candidates.
                guarded = min((current, dp_only), key=seam_count)
                checked = None
                if len(graph.nodes) == 10:
                    checked = current == reduce_crossings(sub, unwind=True, optimize_seams=True, algo2=True)
            except (ValueError, AttributeError, RuntimeError, gp.GurobiError) as exc:
                yield {**common, "variant": "input", "status": type(exc).__name__,
                       "solver_errno": getattr(exc, "errno", None)}
                continue
        for name, result in (("no_processing", rotated), ("dp_only", dp_only),
                             ("current_unwind_dp", current), ("guarded_choice", guarded)):
            coords = api.assign_coordinates(sub, result)
            routes, bounds = torus_routes(paths, sub, result, coords)
            yield {**common, "variant": name, "status": "ok", "seam_segments": seam_count(result),
                   "native_equivalence_check": checked, **route_metrics(routes, bounds)}


def license_cases():
    configurations = (
        ("linear_variables", 2000, 0, False),
        ("linear_variables", 2001, 0, False),
        ("linear_constraints", 1, 2000, False),
        ("linear_constraints", 1, 2001, False),
        ("quadratic_variables", 200, 0, True),
        ("quadratic_variables", 201, 0, True),
    )
    with use_local_license(), create_gurobi_env() as env:
        for variant, nvars, nconstraints, quadratic in configurations:
            with gp.Model(env=env) as model:
                model.Params.Threads = 1
                x = model.addVars(nvars, lb=0, ub=1)
                if quadratic:
                    model.setObjective(gp.quicksum(v * v for v in x.values()))
                else:
                    model.setObjective(gp.quicksum(x.values()))
                for i in range(nconstraints):
                    model.addConstr(x[0] <= 1 + i)
                status, code = "ok", None
                try:
                    model.optimize()
                except gp.GurobiError as exc:
                    status, code = "error", exc.errno
                yield {"variant": variant, "variables": model.NumVars, "constraints": model.NumConstrs,
                       "status": status, "solver_status": model.Status, "solver_errno": code}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--solver-seconds", type=float, default=2)
    parser.add_argument("--seam-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    if args.seam_only:
        write_csv(args.output / "guarded_seams.csv", list(guarded_seams(args.manifest, args.solver_seconds)))
        return
    write_csv(args.output / "license.csv", list(license_cases()))
    output = list(fixed_period_cases(args.manifest, args.solver_seconds))
    write_csv(args.output / "fixed_period.csv", output)


if __name__ == "__main__":
    main()
