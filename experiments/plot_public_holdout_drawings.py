"""Render paired public-network layouts using the archived input graphs."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from matplotlib import pyplot as plt

from plot_framework_examples import draw, node_positions
from torus_study.framework import graphviz, torus
from torus_study.stages import record_solver
from torus_study.validation_inputs import previous_case


def render(task):
    row, archived, settings, output = task
    case = previous_case(row)
    fig, axes = plt.subplots(2, 1, figsize=(12, 9.5), layout="constrained")
    fig.suptitle(f"{case.id}   |   {len(case.graph.nodes)} vertices, {len(case.graph.edges)} edges",
                 fontsize=15, color="#17334a")
    results = {}
    for ax, method, label in zip(axes, ("torus", "dot"), ("Torus", "Graphviz dot"), strict=True):
        saved = archived[method]
        if saved["status"] != "ok":
            ax.set_axis_off()
            ax.text(.5, .5, f"{label}\nOriginal run: {saved['status']} ({saved['wall_seconds']:.2f} s)",
                    transform=ax.transAxes, ha="center", va="center", fontsize=15)
            results[method] = {"status": saved["status"]}
            continue
        if method == "torus":
            with record_solver(settings, []):
                metrics, (routes, bounds) = torus(case.graph)
            layers = metrics["layers"]
        else:
            metrics, (routes, bounds) = graphviz(case.graph, settings.dot, 8)
            layers = len({x for x, _ in node_positions(routes, bounds).values()})
        crossings = metrics["geometric_crossings"]
        equal = all(metrics[key] == saved[key] for key in ("geometric_crossings", "bends"))
        draw(ax, label, routes, bounds, crossings, layers)
        if not equal:
            ax.set_title(ax.get_title() + f"\nReplay; original: {saved['geometric_crossings']} crossings")
        results[method] = {"status": "ok", "geometric_crossings": crossings, "bends": metrics["bends"],
                           "matches_recorded_counts": equal}
    path = output / f"{case.id}.png"
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    return {"case": case.id, "figure": path.name, **results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.study / "inputs.jsonl").open(encoding="utf-8") as source:
        inputs = list(map(json.loads, source))
    archived = {}
    with (args.study / "rows.jsonl").open(encoding="utf-8") as source:
        for row in map(json.loads, source):
            if row["variant"] in ("torus", "dot"):
                archived.setdefault(row["case"], {})[row["variant"]] = row
    settings = SimpleNamespace(**json.loads((args.study / "settings.json").read_text()))
    tasks = ((row, archived[row["id"]], settings, args.output) for row in inputs)
    with (args.output / "drawings.jsonl").open("w", encoding="utf-8") as manifest, ZipFile(
        args.output / "public_network_drawings.zip", "w", compression=ZIP_DEFLATED,
    ) as bundle, ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for result in pool.map(render, tasks):
            print(json.dumps(result), file=manifest, flush=True)
            bundle.write(args.output / result["figure"], result["figure"])
        bundle.write(args.output / "drawings.jsonl", "drawings.jsonl")


if __name__ == "__main__":
    main()
