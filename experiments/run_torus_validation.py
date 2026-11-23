"""Execute the experiments motivated by the first torus-layout report."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import json
import math
import multiprocessing
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from time import perf_counter
import traceback

from run_torus_study import ROOT, append, write_csv

sys.path.insert(0, str(ROOT / "src"))

GROUPS = ("topology", "scc_control", "public", "public_retry", "budget", "ranks", "winding", "sifting", "seams",
          "seam_stress", "coordinates", "coordinate_audit", "scaling", "subdivision", "geometry")


class BudgetExpired(TimeoutError):
    pass


@contextmanager
def wall_budget(seconds):
    def expired(*_):
        raise BudgetExpired()

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class Measurements:
    def __init__(self, info, args):
        self.rows = []
        self.common = {k: v for k, v in info.items()
                       if k not in ("graph", "in_degrees", "out_degrees", "reciprocal_pairs")}
        self.common["case"] = self.common.pop("id")
        self.args = args
        self.setup_limited = False

    def __call__(self, variant, function, *, budget=None):
        import gurobipy as gp
        from torus_study.stages import record_solver

        trace = []
        start = perf_counter()
        return_value = None
        try:
            with wall_budget(budget or self.args.wall_seconds), record_solver(self.args, trace):
                result, return_value = function()
        except BudgetExpired:
            result = {"status": "wall_timeout"}
        except (AttributeError, ArithmeticError, OSError, RuntimeError, ValueError,
                subprocess.SubprocessError, gp.GurobiError) as exc:
            site = traceback.extract_tb(exc.__traceback__)[-1]
            result = {"status": "error", "error_type": type(exc).__name__,
                      "error_location": f"{Path(site.filename).name}:{site.lineno}"}
            code = getattr(exc, "errno", None)
            if isinstance(code, int):
                result["solver_errno"] = code
                if code == gp.GRB.Error.SIZE_LIMIT_EXCEEDED:
                    result["status"] = "license_size_limit"
        limited = any(s["status"] in (9, 13, 16) for s in trace)
        self.rows.append({**self.common, "variant": variant, "status": "ok", **result,
                          "wall_seconds": perf_counter()-start, "solver": trace,
                          "solver_limited": limited or self.setup_limited})
        if variant.startswith("setup"):
            self.setup_limited |= limited
        return return_value


def perform(arg):
    trial, settings = arg
    from torus_study import validation_stages

    info = trial.record()
    run = Measurements(info, argparse.Namespace(**settings))
    function = "topology" if trial.group == "scc_control" else trial.group
    getattr(validation_stages, function)(trial, run)
    return info, run.rows


def wls_probe():
    import gurobipy as gp
    from torus_layout.layering.lib.solver import create_gurobi_env

    start = perf_counter()
    try:
        with wall_budget(6), create_gurobi_env() as env, gp.Model(env=env) as model:
            model.Params.TimeLimit = 1
            x = model.addVars(201, lb=0, ub=1)
            model.setObjective(gp.quicksum(v*v for v in x.values()))
            model.optimize()
            return {"status": "ok", "solver_status": model.Status, "wall_seconds": perf_counter()-start}
    except BudgetExpired:
        return {"status": "wall_timeout", "wall_seconds": perf_counter()-start}
    except gp.GurobiError as exc:
        reason = "name_resolution" if any(k in str(exc).lower() for k in ("resolve host", "resolving host", "dns")) else "solver_or_connection"
        return {"status": reason, "solver_errno": exc.errno, "wall_seconds": perf_counter()-start}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=(*GROUPS, "wls_probe"))
    parser.add_argument("--output", required=True, type=Path, help="New group output directory")
    parser.add_argument("--previous", type=Path, default=ROOT/"output/torus_experiment_20261120")
    parser.add_argument("--public", type=Path, default=ROOT/"output/torus_validation_20261120/sources")
    parser.add_argument("--solver-seconds", type=float, default=1.5)
    parser.add_argument("--wall-seconds", type=float, default=12)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--wls", action="store_true")
    parser.add_argument("--dot", default="dot")
    parser.add_argument("--limit", type=int, help="Stop after the first cases for smoke tests")
    args = parser.parse_args()
    if any(not math.isfinite(x) or x <= 0 for x in (args.solver_seconds,args.wall_seconds)) or args.jobs < 1:
        parser.error("positive finite time bounds and positive job count required")
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(Path("/tmp") / "torus-study-mpl"))
    args.output.mkdir(parents=True)
    revision = subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    from run_torus_study import source_fingerprint

    settings = {"group":args.group, "solver_seconds":args.solver_seconds, "wall_seconds":args.wall_seconds,
                "local_license":not args.wls, "jobs":args.jobs, "dot":shutil.which(args.dot),
                "revision":revision, "source_sha256":source_fingerprint()}
    if settings["dot"]:
        settings["dot_version"] = subprocess.run([settings["dot"],"-V"], capture_output=True,
                                                  text=True, check=True, timeout=5).stderr.strip()
    (args.output/"settings.json").write_text(json.dumps(settings,indent=2)+"\n", encoding="utf-8")
    if args.group == "wls_probe":
        append(args.output/"rows.jsonl", wls_probe())
        return
    if args.group in ("topology","scc_control","budget","public") and not settings["dot"]:
        parser.error("dot is required")
    from torus_study.validation_inputs import trials

    design = list(trials(args.group, args.previous, args.public))
    if args.limit is not None:
        design = design[:args.limit]
    for trial in design:
        append(args.output/"inputs.jsonl", trial.record())
    results = []
    with ProcessPoolExecutor(max_workers=args.jobs, mp_context=multiprocessing.get_context("spawn")) as pool:
        for index, (info, rows) in enumerate(pool.map(perform, ((trial, settings) for trial in design)), 1):
            states = Counter(row["status"] for row in rows)
            for row in rows:
                append(args.output/"rows.jsonl", row)
                results.append({key: value for key,value in row.items() if key != "solver"})
            print(f"{args.group} {index}/{len(design)} {info['id']} {dict(states)}", flush=True)
    write_csv(args.output/"results.csv", results)


if __name__ == "__main__":
    main()
