"""Draw a recorded exhaustive witness and the sifting result side by side."""

import argparse
import json
from pathlib import Path

from matplotlib import pyplot as plt

from torus_layout.coordinates import assign_coordinates
from torus_layout.crossing.global_sifting import sift_blocks
from torus_layout.crossing.initialization import initial_orders
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_study.geometry import route_metrics, torus_routes
from torus_study.stages import subdivision_metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.rows.open(encoding="utf-8") as source:
        row, = [r for r in map(json.loads, source) if (r["width"], r["seed"]) == (3, 962)]
    graph = Graph(tuple(row["nodes"]), tuple(map(tuple, row["edges"])))
    ranks = {u: u // row["width"] for u in graph.nodes}
    flags = {(u, v): ranks[u] > ranks[v] for u, v in graph.edges}
    sub = insert_dummy_nodes(graph, LayerAssignmentResult(ranks, flags, 0))
    layers = sorted(sub.layers)
    initial = initial_orders(sub.layers, layers, list(sub.graph.edges))[0]
    witness = CrossingResult(
        {int(k): v for k, v in row["witness_order"].items()},
        dict(zip(graph.edges, row["witness_windings"], strict=True)),
    )
    paths, _ = subdivision_metrics(graph, sub)
    fig, axes = plt.subplots(1, 2, figsize=(8, 4.4), layout="constrained")
    for ax, (label, embedding, expected) in zip(axes, (
        ("Global sifting", CrossingResult(*sift_blocks(sub, initial, layers, 5)),
         row["crossings_by_pass_limit"]["5"]),
        ("Exhaustive witness", witness, row["minimum_winding_1"]),
    ), strict=True):
        coords = assign_coordinates(sub, embedding, method="brandes_koepf_blocks")
        routes, bounds = torus_routes(paths, sub, embedding, coords)
        metrics = route_metrics(routes, bounds)
        crossings = metrics["geometric_crossings"]
        if crossings != expected:
            raise ValueError(f"{label}: expected {expected} crossings, got {crossings}")
        print(json.dumps({"layout": label, **metrics}))
        xmin, ymin, width, height = bounds
        for route in routes:
            for start, end in route.pieces:
                ax.plot(*zip(start, end), color="#315a75", alpha=.78, linewidth=1.15)
                if end == coords.positions[route.edge[1]]:
                    ax.annotate("", end, xytext=start, arrowprops={
                        "arrowstyle": "-|>", "color": "#315a75", "shrinkB": 7, "lw": 1.05,
                    })
        for node, (x, y) in coords.positions.items():
            ax.scatter(x, y, color="#182e42", s=185, zorder=3)
            ax.text(x, y, str(node), ha="center", va="center", color="white", fontsize=8, zorder=4)
        ax.set(xlim=(xmin, xmin + width), ylim=(ymin, ymin + height),
               xticks=[], yticks=[], title=f"{label}\n{crossings} geometric crossings")
    fig.savefig(args.output)
    fig.savefig(args.output.with_suffix(".png"), dpi=180)


if __name__ == "__main__":
    main()
