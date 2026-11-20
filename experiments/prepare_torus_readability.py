"""Prepare counterbalanced static trials or summarize collected response CSVs."""

from collections import defaultdict
from itertools import islice, product
from pathlib import Path
from random import Random
from statistics import mean
from types import SimpleNamespace
import argparse
import csv
import json
import math
import os
import sys

from run_torus_study import ROOT, bootstrap, write_csv

CONDITIONS = ("sugiyama", "torus_base", "torus_context")
TASKS = ("direction", "distance")
SIZES = (20, 40)
TRIALS_PER_CELL = 3


def candidates(graph, routes, task):
    import networkx as nx

    seam = {(r.edge) for r in routes if r.x_wraps or r.y_wraps}
    if task == "direction":
        existing = set(graph.edges)
        return [(u, v, 1, (u, v) in seam) for u, v in graph.edges if (v, u) not in existing]

    network = nx.DiGraph(graph.edges)
    options = []
    for u, distances in nx.all_pairs_shortest_path_length(network, cutoff=5):
        for v, distance in distances.items():
            if distance < 2:
                continue
            paths = list(islice(nx.all_shortest_paths(network, u, v), 2))
            if len(paths) == 1:
                wraps = any(e in seam for e in zip(paths[0], paths[0][1:]))
                options.append((u, v, distance, wraps))
    return options


def render(routes, bounds, highlighted, context, destination):
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import FancyArrowPatch, Rectangle

    positions = {node: point for r in routes for node, point in
                 ((r.edge[0], r.points[0]), (r.edge[1], r.pieces[-1][1]))}
    if bounds is None:
        points = [point for route in routes for segment in route.pieces for point in segment]
        xmin, ymin = min(x for x, _ in points), min(y for _, y in points)
        width = max(max(x for x, _ in points) - xmin, 1)
        height = max(max(y for _, y in points) - ymin, 1)
    else:
        xmin, ymin, width, height = bounds
    offsets = [(0, 0)]
    if context:
        offsets = [tile for tile in product((-1, 0, 1), repeat=2) if tile != (0, 0)] + offsets
    fig, ax = plt.subplots(figsize=(10, 7), dpi=130)
    for i, j in offsets:
        dx, dy = i * width, j * height
        central = i == j == 0
        color = "#313131" if central else "#929292"
        ax.add_collection(LineCollection(
            [[(a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)]
             for route in routes for a, b in route.pieces], colors=color, linewidths=0.8,
        ))
        for route in routes:
            start, end = route.pieces[-1]
            ax.add_patch(FancyArrowPatch(
                (start[0] + dx, start[1] + dy), (end[0] + dx, end[1] + dy), arrowstyle="-|>",
                color=color, mutation_scale=11, linewidth=0.8, shrinkA=0, shrinkB=4,
                zorder=2,
            ))
        ax.scatter([x + dx for x, _ in positions.values()], [y + dy for _, y in positions.values()],
                   s=19, color=color, zorder=3)
        for node, label in highlighted.items():
            x, y = positions[node]
            ax.annotate(label, (x + dx, y + dy), xytext=(4, 4), textcoords="offset points",
                        color="#064d97" if central else "#547499", fontsize=10, weight="bold",
                        bbox={"fc": "white", "ec": "none", "pad": 0.4, "alpha": 0.85}, zorder=4)
    if bounds is not None:
        ax.add_patch(Rectangle((xmin, ymin), width, height, fill=False, color="#303030", linewidth=1))
    # Equal viewport and central scale for the two torus conditions.
    ax.set(xlim=(xmin - 0.55*width, xmin + 1.55*width),
           ylim=(ymin + 1.55*height, ymin - 0.55*height), aspect="equal")
    ax.set_axis_off()
    fig.subplots_adjust(left=0.02, bottom=0.02, right=0.98, top=0.98)
    try:
        fig.savefig(destination, facecolor="white")
    finally:
        plt.close(fig)


def prepare(args):
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.path.insert(0, str(ROOT / "src"))
    from torus_study.framework import repository_baseline, torus
    from torus_study.inputs import generate
    from torus_study.stages import record_solver

    args.output.mkdir(parents=True)
    stimuli = args.output / "images"
    stimuli.mkdir()
    trial_rows = []
    audited = []
    for size in SIZES:
        counts = defaultdict(int)
        for seed in range(args.seeds):
            if all(counts[task, wraps] == TRIALS_PER_CELL
                   for task, wraps in product(TASKS, (True, False))):
                break
            case = generate("watts_strogatz", size, 2, seed + 11000)
            trace = []
            with record_solver(SimpleNamespace(solver_seconds=args.solver_seconds,
                                               local_license=args.local_license), trace):
                try:
                    metrics, layout = torus(case.graph)
                except Exception as exc:
                    audited.append({"case": case.id, "status": type(exc).__name__})
                    continue
            valid = layout is not None and all(row["status"] in (2, 3) for row in trace)
            audited.append({"case": case.id, "status": "eligible" if valid else "excluded"})
            if not valid:
                continue
            torus_routes, bounds = layout
            rng = Random(seed + size)
            choices = list(product(TASKS, (True, False)))
            rng.shuffle(choices)
            for task, wraps in choices:
                if counts[task, wraps] == TRIALS_PER_CELL:
                    continue
                options = [candidate for candidate in candidates(case.graph, torus_routes, task)
                           if candidate[-1] == wraps]
                if not options:
                    continue
                u, v, answer, _ = rng.choice(options)
                if task == "direction":
                    if rng.randrange(2):
                        u, v = v, u
                        answer = "B_to_A"
                    else:
                        answer = "A_to_B"
                _, (planar, _) = repository_baseline(case.graph)
                trial = f"{size}-{task}-{int(wraps)}-{counts[task, wraps]}"
                for condition in CONDITIONS:
                    render(planar if condition == "sugiyama" else torus_routes,
                           None if condition == "sugiyama" else bounds,
                           {u: "A", v: "B"}, condition == "torus_context",
                           stimuli / f"{trial}-{condition}.png")
                trial_rows.append({"trial": trial, "case": case.id, "size": size, "task": task,
                                   "wraps": int(wraps), "answer": answer, "a": u, "b": v,
                                   "rotation": counts[task, wraps],
                                   "layout_manifest": json.dumps(case.manifest(), ensure_ascii=False)})
                counts[task, wraps] += 1
                break
    write_csv(args.output / "stimulus_audit.csv", audited)
    write_csv(args.output / "answer_key.csv", trial_rows)
    if len(trial_rows) != len(SIZES) * len(TASKS) * 2 * TRIALS_PER_CELL:
        raise SystemExit("Incomplete stimulus quotas. See stimulus_audit.csv and answer_key.csv.")
    for group in range(len(CONDITIONS)):
        group_rows = []
        order = list(trial_rows)
        Random(20261119 + group).shuffle(order)
        for step, trial in enumerate(order, 1):
            condition = CONDITIONS[(trial["rotation"] + group) % len(CONDITIONS)]
            group_rows.append({
                "step": step, "trial": trial["trial"], "condition": condition,
                "image": f"images/{trial['trial']}-{condition}.png",
                "prompt": "A と B を結ぶ辺の向きはどちらですか（A_to_B / B_to_A）"
                if trial["task"] == "direction" else "A から B までの最短有向経路は何辺ですか",
            })
        write_csv(args.output / f"form_{group}.csv", group_rows)


def load(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def score(args):
    truth = {row["trial"]: row for row in load(args.stimuli / "answer_key.csv")}
    forms = {group: {r["trial"]: r["condition"] for r in load(args.stimuli / f"form_{group}.csv")}
             for group in range(len(CONDITIONS))}
    seen = set()
    participant_groups = {}
    interrupted_people = set()
    grouped = defaultdict(list)
    for row in load(args.responses):
        person, trial = row["participant"].strip(), row["trial"]
        group = int(row["group"])
        if not person or group not in forms or trial not in forms[group] or (person, trial) in seen:
            raise ValueError("invalid or duplicate trial response")
        if participant_groups.setdefault(person, group) != group:
            raise ValueError("multiple group assignments for one participant")
        seconds = float(row["seconds"])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("invalid response time")
        interruption = row.get("interrupted") or "0"
        if interruption not in ("0", "1"):
            raise ValueError("invalid interruption flag")
        if interruption == "1":
            interrupted_people.add(person)
        seen.add((person, trial))
        item = truth[trial]
        condition = forms[group][trial]
        correct = row["answer"].strip() == item["answer"]
        for wrap_scope in ("all", item["wraps"]):
            grouped[item["task"], wrap_scope, "accuracy", person, condition].append(int(correct))
            if correct:
                grouped[item["task"], wrap_scope, "correct_seconds", person, condition].append(seconds)
    complete_people = {person for person, group in participant_groups.items()
                       if all((person, trial) in seen for trial in forms[group])}
    excluded = complete_people & interrupted_people if args.exclude_interrupted else set()
    eligible = complete_people - excluded
    results = []
    for task, scope, metric in product(TASKS, ("all", "0", "1"), ("accuracy", "correct_seconds")):
        for treatment, control in (("torus_context", "torus_base"),
                                   ("torus_context", "sugiyama"), ("torus_base", "sugiyama")):
            differences = []
            for person in sorted(eligible):
                left = grouped.get((task, scope, metric, person, treatment), [])
                right = grouped.get((task, scope, metric, person, control), [])
                if left and right:
                    differences.append(mean(left) - mean(right))
            low, high = bootstrap(differences, 5000)
            results.append({"task": task, "torus_path_wraps": scope, "metric": metric,
                            "treatment": treatment, "control": control,
                            "participants": len(participant_groups),
                            "complete_participants": len(complete_people),
                            "excluded_interrupted_participants": len(excluded),
                            "paired_participants": len(differences),
                            "delta_mean": mean(differences) if differences else None,
                            "ci_low": low, "ci_high": high})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, results[0])
        writer.writeheader()
        writer.writerows(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--seeds", type=int, default=100)
    build.add_argument("--solver-seconds", type=float, default=15)
    build.add_argument("--local-license", action="store_true")
    analyze = commands.add_parser("score")
    analyze.add_argument("--stimuli", required=True, type=Path)
    analyze.add_argument("--responses", required=True, type=Path)
    analyze.add_argument("--output", required=True, type=Path)
    analyze.add_argument("--exclude-interrupted", action="store_true",
                         help="Exclude participants with any interrupted timed item")
    args = parser.parse_args()
    if args.command == "prepare":
        if args.seeds <= 0 or not math.isfinite(args.solver_seconds) or args.solver_seconds <= 0:
            parser.error("seed count and time limit must be positive")
        prepare(args)
    else:
        score(args)


if __name__ == "__main__":
    main()
