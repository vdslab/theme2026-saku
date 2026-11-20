"""Run the reproducible torus layout experiment suite from the repository root."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import argparse
import csv
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
from random import Random
import shutil
import signal
from statistics import mean, median
import subprocess
import sys
from time import perf_counter
import traceback

ROOT = Path(__file__).resolve().parents[1]
VERSION = 3
GROUPS = ("framework", "layering", "subdivision", "crossing", "coordinates", "drawing", "oracles", "scaling")
FRAMEWORK_VARIANTS = {
    "torus": "sugiyama", "sugiyama": "sugiyama", "radial": "sugiyama", "dot": "sugiyama",
    "sugiyama_1981": "sugiyama_1981",
    "torus_without_unwind_or_dp": "torus", "cylindrical_reference": "torus",
}
EXTERNAL_FRAMEWORKS = ("dot", "twopi", "circo", "sfdp", "elk")
FRAMEWORK_VARIANTS.update({tool: tool for tool in EXTERNAL_FRAMEWORKS[1:]})
PRIMARY_CONTRASTS = {
    "framework": (("torus", "radial"), *(("torus", tool) for tool in EXTERNAL_FRAMEWORKS)),
    "sifting": (("default", "no_guard"), ("default", "fixed_winding")),
    "coordinates": (("bk", "bk_no_smooth"), ("bk_no_smooth", "uniform"),
                    ("uniform_smooth", "uniform"), ("lp_bend_1", "lp")),
    "crossing_step": (("unwind_1_dp_1", "unwind_1_dp_0"),
                      ("unwind_1_dp_1", "unwind_0_dp_1")),
}


def payload(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def append(path, value):
    with path.open("a", encoding="utf-8") as file:
        file.write(payload(value) + "\n")


def read_lines(path):
    if path.is_file():
        with path.open(encoding="utf-8") as file:
            for line in file:
                if line.endswith("\n"):
                    yield json.loads(line)


class Recorder:
    def __init__(self, path):
        self.path = path
        self.trace = []
        self.outcome = {}
        self.input_limited = False

    def __call__(self, experiment, variant, baseline, evaluate):
        common = {"experiment": experiment, "variant": variant, "baseline": baseline}
        append(self.path, {**common, "status": "running"})
        self.trace.clear()
        started = perf_counter()
        value = None
        try:
            metrics, value = evaluate()
        except Exception as exc:
            site = traceback.extract_tb(exc.__traceback__)[-1]
            metrics = {"status": "error", "error_type": type(exc).__name__,
                       "error_location": f"{Path(site.filename).name}:{site.lineno}"}
        limited = any(row["status"] in (9, 13) for row in self.trace)
        self.outcome = {
            **common, "status": "ok", "wall_seconds": perf_counter() - started, **metrics,
            "solver_calls": len(self.trace),
            "solver_limited": limited,
            "input_solver_limited": self.input_limited,
            "solver": self.trace.copy(),
        }
        append(self.path, self.outcome)
        if experiment == "input" or (experiment == "search" and variant == "binary"):
            self.input_limited = limited
        return value


def dispatch(args, manifest, events):
    # Set by the parent before any scientific libraries are loaded.
    sys.path.insert(0, str(ROOT / "src"))
    from torus_layout.models import Graph
    from torus_study import framework, stages
    from torus_study.inputs import Case

    case = Case(manifest["id"], manifest["family"], manifest["seed"],
                Graph(tuple(manifest["graph"]["nodes"]), tuple(map(tuple, manifest["graph"]["edges"]))))
    run = Recorder(events)
    with stages.record_solver(args, run.trace):
        if args.group == "framework":
            framework.framework_study(case.graph, run, args)
        elif args.group == "scaling":
            framework.scaling_study(case.graph, run)
        elif args.group == "oracles":
            stages.oracle_study(case, run)
        elif args.group == "drawing":
            stages.drawing_study(case, run, args.output / "images")
        else:
            functions = {"layering": stages.layer_study, "subdivision": stages.subdivision_study,
                         "crossing": stages.crossing_study, "coordinates": stages.coordinate_study}
            functions[args.group](case.graph, run)


def worker():
    manifest = json.loads(sys.stdin.read())
    args = argparse.Namespace(**manifest.pop("settings"))
    args.output = Path(args.output)
    events = Path(manifest.pop("events"))
    dispatch(args, manifest, events)


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as file:
        if fields:
            writer = csv.DictWriter(file, fields)
            writer.writeheader()
            writer.writerows(rows)


def worker_rows(args, case, settings, path):
    manifest = {**case, "settings": settings, "events": str(path)}
    status = "ok"
    started = perf_counter()
    with subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker"], stdin=subprocess.PIPE,
        encoding="utf-8", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=ROOT, start_new_session=True,
        env={**os.environ, "MPLBACKEND": "Agg", "PYTHONHASHSEED": "0"},
    ) as process:
        try:
            process.communicate(payload(manifest), timeout=args.case_seconds)
            if process.returncode != 0:
                status = f"worker_exit_{process.returncode}"
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            if isinstance(exc, KeyboardInterrupt):
                raise
            status = "case_timeout"
    latest = {}
    for row in read_lines(path):
        latest[row["experiment"], row["variant"]] = row
    for row in latest.values():
        if row["status"] == "running":
            row["status"] = status if status != "ok" else "incomplete"
    return list(latest.values()), status, perf_counter() - started


def child_rows(args, case, index):
    forwarded = ("group", "local_license", "solver_seconds", "comparison_seconds",
                 "dot", "graphviz", "node", "elkjs", "output")
    settings = {key: getattr(args, key) for key in forwarded}
    settings["output"] = str(settings["output"])
    variants = (None,)
    if args.group == "framework":
        external = ["dot"] if args.dot else []
        if args.graphviz:
            external.extend(("twopi", "circo", "sfdp"))
        if args.elkjs:
            external.append("elk")
        variants = ("torus", *external) if args.external_only else tuple(
            name for name in FRAMEWORK_VARIANTS if name not in EXTERNAL_FRAMEWORKS or name in external
        )
    rows, workers = [], {}
    for variant in variants:
        path = args.output / "workers" / f"{index:05}-{variant or args.group}.jsonl"
        baseline = variant if args.external_only else FRAMEWORK_VARIANTS.get(variant)
        variant_settings = {**settings, "variant": variant, "baseline": baseline}
        measurements, status, seconds = worker_rows(args, case, variant_settings, path)
        if not measurements and variant is not None:
            measurements.append({"experiment": args.group, "variant": variant,
                                 "baseline": baseline,
                                 "status": status if status != "ok" else "incomplete"})
        rows.extend(measurements)
        workers[variant or args.group] = {"status": status, "worker_seconds": seconds}
    return rows, {
        "case": case["id"], "family": case["family"],
        "status": next((worker["status"] for worker in workers.values() if worker["status"] != "ok"), "ok"),
        "worker_seconds": sum(worker["worker_seconds"] for worker in workers.values()),
        "recorded_variants": len(rows),
        "workers": payload(workers),
    }


def source_fingerprint():
    paths = [
        *(ROOT / "src").rglob("*.py"),
        *(ROOT / "experiments" / "torus_study").glob("*.py"),
        *(ROOT / "experiments" / "torus_study").glob("*.cjs"),
        Path(__file__),
    ]
    digest = sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


INPUT_FIELDS = {"nodes", "edges", "seed", "scc_count", "largest_scc_fraction", "cyclic_node_fraction"}


def bootstrap(values, repeats):
    if len(values) < 2:
        return None, None
    rng = Random(20261119)
    estimates = sorted(mean(rng.choices(values, k=len(values))) for _ in range(repeats))
    return estimates[int(0.025 * (repeats - 1))], estimates[int(0.975 * (repeats - 1))]


def paired_summary(rows, repeats):
    groups = defaultdict(dict)
    for row in rows:
        for key in ("all", row["family"], row["cycle_scope"],
                    f"{row['family']}/{row['nodes']}/{row['edges']}"):
            groups[(row["experiment"], key)][row["case"], row["variant"]] = row
    for (experiment, scope), records in groups.items():
        variants = {(row["variant"], row["baseline"]) for row in records.values()
                    if row["variant"] != row["baseline"]}
        variants.update(PRIMARY_CONTRASTS.get(experiment, ()))
        if experiment == "framework" and scope == "acyclic":
            variants.add(("torus", "sugiyama_1981"))
        cases = {case for case, _ in records}
        for variant, baseline in sorted(variants):
            pairs = []
            for case in sorted(cases):
                treatment = records.get((case, variant), {})
                control = records.get((case, baseline), {})
                if treatment.get("status") == control.get("status") == "ok":
                    pairs.append((treatment, control))
            measurements = {key for left, right in pairs for key in left.keys() & right.keys()
                            if key not in INPUT_FIELDS and numeric(left[key]) and numeric(right[key])}
            for metric in sorted(measurements):
                deltas = [left[metric] - right[metric] for left, right in pairs
                          if numeric(left.get(metric)) and numeric(right.get(metric))]
                low, high = bootstrap(deltas, repeats)
                yield {"experiment": experiment, "scope": scope, "variant": variant,
                       "baseline": baseline, "metric": metric, "cases_seen": len(cases),
                       "pairs": len(deltas), "delta_mean": mean(deltas), "delta_median": median(deltas),
                       "ci_low": low, "ci_high": high,
                       "decreased": sum(d < -1e-9 for d in deltas),
                       "unchanged": sum(abs(d) <= 1e-9 for d in deltas),
                       "increased": sum(d > 1e-9 for d in deltas),
                       "pairs_with_limited_solver": sum(
                           any(row.get(key) for row in (left, right)
                               for key in ("solver_limited", "input_solver_limited"))
                           for left, right in pairs if numeric(left.get(metric)) and numeric(right.get(metric))
                       )}


def descriptive(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["experiment"], row["variant"], row["family"], row["nodes"], row["edges"])].append(row)
    for (experiment, variant, family, nodes, edges), records in groups.items():
        counts = Counter(row["status"] for row in records)
        keys = {k for row in records if row["status"] == "ok" for k, v in row.items()
                if k not in INPUT_FIELDS and numeric(v)}
        common = {"experiment": experiment, "variant": variant, "family": family,
                  "nodes": nodes, "edges": edges, "attempted": len(records),
                  "ok": counts["ok"], "statuses": payload(dict(counts))}
        yield common
        for key in sorted(keys):
            values = sorted(row[key] for row in records if row["status"] == "ok" and numeric(row.get(key)))
            yield {**common, "metric": key, "observations": len(values), "median": median(values),
                   "p90": values[math.ceil(0.9 * len(values)) - 1],
                   "min": values[0], "max": values[-1]}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=GROUPS)
    parser.add_argument("--profile", choices=("quick", "main"), default="quick")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--local-license", action="store_true")
    parser.add_argument("--dot", metavar="EXECUTABLE", help="Enable Graphviz dot only")
    parser.add_argument("--graphviz", nargs="?", const="dot", metavar="EXECUTABLE",
                        help="Enable Graphviz dot, twopi, circo, and sfdp")
    parser.add_argument("--elkjs", metavar="PACKAGE_DIR", help="Enable ELK Layered using an installed elkjs package")
    parser.add_argument("--external-only", action="store_true",
                        help="Compare the proposed torus pipeline with external tools only")
    parser.add_argument("--benchmark", action="append", default=[], metavar="FAMILY=GRAPHML_DIR")
    parser.add_argument("--benchmark-only", action="store_true", help="Skip generated cases")
    parser.add_argument("--solver-seconds", type=float, default=15)
    parser.add_argument("--comparison-seconds", type=float, default=60)
    parser.add_argument("--case-seconds", type=float, default=600)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--limit", type=int, help="Run only the first N cases")
    parser.add_argument("--sizes", type=int, nargs="+", help="Override generated graph vertex counts")
    parser.add_argument("--densities", type=int, nargs="+", choices=(2, 4), help="Override edges per vertex")
    parser.add_argument("--seed-count", type=int, help="Override number of seeds per generated condition")
    parser.add_argument("--jobs", type=int, default=1, help="Maximum number of concurrent case workers")
    args = parser.parse_args()
    if any(not math.isfinite(value) or value <= 0 for value in
           (args.solver_seconds, args.comparison_seconds, args.case_seconds)):
        parser.error("time limits must be positive")
    if args.bootstrap <= 0 or (args.limit is not None and args.limit <= 0):
        parser.error("repetition counts must be positive")
    if args.jobs <= 0 or (args.seed_count is not None and args.seed_count <= 0):
        parser.error("jobs and seed count must be positive")
    if args.group in ("drawing", "oracles") and (args.sizes or args.densities or args.seed_count):
        parser.error("drawing and oracles use fixed case designs")
    if args.sizes and (min(args.sizes) < 2 * max(args.densities or (2, 4)) + 2
                       or len(set(args.sizes)) != len(args.sizes)):
        parser.error("sizes must be distinct and at least 2 * max(densities) + 2")
    if args.densities and len(set(args.densities)) != len(args.densities):
        parser.error("densities must be distinct")
    if args.group != "framework" and (args.graphviz or args.elkjs or args.external_only):
        parser.error("--graphviz, --elkjs and --external-only require the framework group")
    args.dot = args.dot or args.graphviz
    for option in ("dot", "graphviz"):
        if executable := getattr(args, option):
            resolved = shutil.which(executable)
            if resolved is None:
                parser.error(f"Graphviz executable not found: {executable}")
            setattr(args, option, resolved)
    args.node = shutil.which("node") if args.elkjs else None
    if args.elkjs:
        package = Path(args.elkjs).resolve()
        try:
            info = json.loads((package / "package.json").read_text(encoding="utf-8"))
            if info["name"] != "elkjs" or not info["version"]:
                raise ValueError("expected an elkjs package")
        except (OSError, ValueError, KeyError) as exc:
            parser.error(f"invalid elkjs package directory: {exc}")
        if not args.node:
            parser.error("Node.js is required for --elkjs")
        args.elkjs = str(package)
        args.elkjs_version = info["version"]
    if args.external_only and not (args.dot or args.elkjs):
        parser.error("--external-only requires --graphviz, --dot or --elkjs")
    if args.benchmark and args.group not in ("framework", "layering", "subdivision", "crossing", "coordinates"):
        parser.error("this group does not use public benchmark inputs")
    if args.benchmark_only and not args.benchmark:
        parser.error("--benchmark-only requires --benchmark")
    if args.output.exists():
        parser.error("output directory already exists")
    args.output = args.output.resolve()
    return args


def evaluate_cases(cases, args):
    from itertools import islice

    indexed = enumerate(cases)
    if args.jobs == 1:
        for index, case in indexed:
            manifest = case.manifest()
            yield index, case, manifest, child_rows(args, manifest, index)
        return
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        while batch := list(islice(indexed, args.jobs)):
            submissions = []
            for index, case in batch:
                manifest = case.manifest()
                submissions.append((index, case, manifest, pool.submit(child_rows, args, manifest, index)))
            for index, case, manifest, submission in submissions:
                yield index, case, manifest, submission.result()


def main():
    args = parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from importlib.metadata import version
    from itertools import chain, islice
    from torus_study.inputs import generated_cases, public_cases

    benchmarks, audit = [], []
    for specification in args.benchmark:
        name, _, path = specification.partition("=")
        if name not in ("att", "rome", "dagmar") or not path:
            raise SystemExit(f"invalid benchmark selector: {specification}")
        if any(case.family == name for case in benchmarks):
            raise SystemExit(f"duplicate benchmark selector: {name}")
        selected, files = public_cases(Path(path), name)
        benchmarks.extend(selected)
        audit.extend(files)

    args.output.mkdir(parents=True)
    (args.output / "workers").mkdir()
    write_csv(args.output / "benchmark_audit.csv", audit)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout.strip()
    dot_version = None
    if args.dot:
        dot_version = subprocess.run([args.dot, "-V"], capture_output=True, text=True,
                                     timeout=args.comparison_seconds, check=False).stderr.strip()
    graphviz_version = None
    if args.graphviz:
        graphviz_version = subprocess.run(
            [args.graphviz, "-V"], capture_output=True, text=True,
            timeout=args.comparison_seconds, check=True,
        ).stderr.strip()
    settings = {**vars(args), "output": str(args.output), "suite_version": VERSION,
                "graphviz_version": graphviz_version,
                "revision": revision, "platform": platform.platform(), "dot_version": dot_version,
                "source_sha256": source_fingerprint(),
                "python": platform.python_version(),
                "packages": {p: version(p) for p in ("networkx", "gurobipy", "matplotlib", "pillow")}}
    (args.output / "settings.json").write_text(payload(settings) + "\n", encoding="utf-8")

    records, cases = [], []
    generated = generated_cases(args.group, args.profile, sizes=args.sizes, densities=args.densities,
                                seed_count=args.seed_count)
    inputs = iter(benchmarks) if args.benchmark_only else chain(generated, benchmarks)
    if args.limit is not None:
        inputs = islice(inputs, args.limit)
    for index, case, manifest, (rows, progress) in evaluate_cases(inputs, args):
        append(args.output / "inputs.jsonl", manifest)
        append(args.output / "case_progress.jsonl", progress)
        cases.append(progress)
        cycle_scope = ("acyclic" if manifest["cyclic_node_fraction"] == 0 else
                       "strongly_connected" if manifest["scc_count"] == 1 else "cyclic_multiple_scc")
        for row in rows:
            flat = {"case": case.id, "family": case.family, "seed": case.seed,
                    "cycle_scope": cycle_scope,
                    **{key: manifest[key] for key in sorted(INPUT_FIELDS)}, **row}
            append(args.output / "rows.jsonl", flat)
            flat.pop("solver", None)
            records.append(flat)
        print(f"{index + 1} {case.id} {progress['status']}", flush=True)

    write_csv(args.output / "results.csv", records)
    write_csv(args.output / "cases.csv", cases)
    write_csv(args.output / "summary.csv", list(descriptive(records)))
    write_csv(args.output / "paired.csv", list(paired_summary(records, args.bootstrap)))


if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        worker()
    else:
        main()
