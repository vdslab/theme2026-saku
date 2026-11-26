"""Reproduce four-method drawing examples and count occupied dot columns."""

import argparse
import csv
import json
from pathlib import Path
from types import SimpleNamespace

from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection

from torus_study.framework import graphviz, repository_baseline, torus
from torus_study.stages import record_solver
from torus_study.validation_inputs import previous_case


METHODS = (
    ("torus", "Torus"),
    ("sugiyama", "Sugiyama"),
    ("radial", "Radial"),
    ("dot", "Graphviz dot"),
)


def node_positions(routes, bounds):
    positions = {}
    for route in routes:
        for node, (x, y) in zip(route.edge, (route.points[0], route.points[-1]), strict=True):
            if bounds:
                xmin, ymin, width, height = bounds
                x, y = (x - xmin) % width + xmin, (y - ymin) % height + ymin
            positions[node] = (x, y)
    return positions


def draw(ax, title, routes, bounds, crossings, layers):
    positions = node_positions(routes, bounds)
    for route in routes:
        wrapped = bool(route.x_wraps or route.y_wraps)
        color = "#b65028" if wrapped else "#496074"
        ax.add_collection(LineCollection(route.pieces, colors=color, linewidths=1.05,
                                         linestyles="dashed" if wrapped else "solid", alpha=.8))
        target = positions[route.edge[1]]
        # Use the last nonzero segment ending at the target for the arrowhead.
        for start, end in reversed(route.pieces):
            if abs(end[0] - target[0]) + abs(end[1] - target[1]) < 1e-6 and start != end:
                ax.annotate("", xy=end, xytext=start,
                            arrowprops={"arrowstyle": "-|>", "color": color, "lw": .85,
                                        "mutation_scale": 9, "shrinkA": 0, "shrinkB": 5})
                break
    for node, (x, y) in positions.items():
        ax.scatter(x, y, s=170, facecolor="#f2f6f8", edgecolor="#17334a", zorder=4)
        ax.text(x, y, str(node), ha="center", va="center", fontsize=7.5, color="#17334a", zorder=5)
    if bounds:
        xmin, ymin, width, height = bounds
        ax.set(xlim=(xmin, xmin + width), ylim=(ymin, ymin + height), xticks=[], yticks=[])
    else:
        ax.autoscale()
        ax.margins(.09)
        ax.set_axis_off()
    ax.set_aspect("equal", adjustable="box")
    scope = "occupied columns" if title == "Graphviz dot" else "layers"
    ax.set_title(f"{title}\n{crossings} crossings  |  {layers} {scope}", fontsize=12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("cases", nargs="+")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.study / "results.csv").open() as source:
        saved = {(r["case"], r["variant"]): r for r in csv.DictReader(source)
                 if r["experiment"] == "framework" and r["status"] == "ok"}
    settings = SimpleNamespace(**json.loads((args.study / "settings.json").read_text()))
    with (args.study / "inputs.jsonl").open() as source:
        cases = [previous_case(row) for row in map(json.loads, source)]

    with (args.output / "dot_layers.jsonl").open("w") as destination:
        for case in cases:
            dot_metrics, (dot_routes, _) = graphviz(case.graph, settings.dot, settings.comparison_seconds)
            dot_columns = len({x for x, _ in node_positions(dot_routes, None).values()})
            if dot_metrics["geometric_crossings"] != int(saved[case.id, "dot"]["geometric_crossings"]):
                raise ValueError(f"Graphviz crossing count changed for {case.id}")
            print(json.dumps({"case": case.id, "occupied_columns": dot_columns,
                              "geometric_crossings": dot_metrics["geometric_crossings"]}), file=destination)
            if case.id not in args.cases:
                continue
            with record_solver(settings, []):
                torus_result = torus(case.graph)
            measurements = {
                "torus": torus_result,
                "sugiyama": repository_baseline(case.graph),
                "radial": repository_baseline(case.graph, radial=True),
                "dot": (dot_metrics, (dot_routes, None)),
            }
            fig, axes = plt.subplots(2, 2, figsize=(11.2, 9.0), layout="constrained")
            fig.suptitle(f"{case.id}   |   {len(case.graph.nodes)} vertices, {len(case.graph.edges)} edges",
                         fontsize=15, color="#17334a")
            for ax, (method, title) in zip(axes.flat, METHODS, strict=True):
                metrics, (routes, bounds) = measurements[method]
                crossings = metrics["geometric_crossings"]
                historical = saved[case.id, method]
                if crossings != int(historical["geometric_crossings"]):
                    raise ValueError(f"{case.id}/{method}: crossing count changed")
                layers = dot_columns if method == "dot" else metrics["layers"]
                if method != "dot" and layers != int(historical["layers"]):
                    raise ValueError(f"{case.id}/{method}: layer count changed")
                draw(ax, title, routes, bounds, crossings, layers)
            fig.savefig(args.output / f"{case.id}.png", dpi=175, facecolor="white")
            plt.close(fig)
            print(f"{case.id}: all four drawings match recorded crossing counts")


if __name__ == "__main__":
    main()
