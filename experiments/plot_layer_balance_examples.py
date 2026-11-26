"""Recreate paired drawings from the layer-balance study."""

import argparse
import csv
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

from matplotlib import pyplot as plt
from PIL import Image

from torus_layout.coordinates import assign_coordinates
from torus_layout.crossing import reduce_crossings
from torus_layout.drawing import DrawingOptions, create_figure
from torus_layout.layering import balance_layers
from torus_layout.subdivision import insert_dummy_nodes
from torus_study.geometry import route_metrics, torus_routes
from torus_study.stages import assignment_metrics, record_solver, subdivision_metrics
from torus_study.validation_inputs import previous_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("cases", nargs="+")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.study / "results.csv").open() as source:
        data = {(r["case"], r["experiment"], r["variant"]): r for r in csv.DictReader(source)}
    with (args.study / "inputs.jsonl").open() as source:
        inputs = {r["id"]: r for r in map(json.loads, source)}
    settings = json.loads((args.study / "settings.json").read_text())

    for case in args.cases:
        graph = previous_case(inputs[case]).graph
        panels = []
        for method, title in (("diff", "Linear span sum"), ("diff_square", "Squared span sum")):
            saved = data[case, "balance", method]
            layers, wraps = int(saved["layers"]), int(saved["rank_wrap_edges"])
            with record_solver(SimpleNamespace(**settings), []):
                assignment = balance_layers(graph, wraps, layers, method)
            ranking = assignment_metrics(graph, assignment, layers, wraps)
            sub = insert_dummy_nodes(graph, assignment)
            crossing = reduce_crossings(sub)
            coordinates = assign_coordinates(sub, crossing)
            paths, _ = subdivision_metrics(graph, sub)
            routes, bounds = torus_routes(paths, sub, crossing, coordinates)
            drawing = route_metrics(routes, bounds)
            downstream = data[case, "balance_downstream", method]
            for key in ("span_sum", "span_square_sum", "max_span", "predicted_dummies"):
                if ranking[key] != int(saved[key]):
                    raise ValueError(f"{case}/{method}: changed {key}")
            for key in ("geometric_crossings", "bends", "either_seam_edges"):
                if drawing[key] != int(downstream[key]):
                    raise ValueError(f"{case}/{method}: changed {key}")
            fig = create_figure(sub, crossing, coordinates, options=DrawingOptions(
                figsize=(7.2, 5.5), draw_dummy_nodes=True, align_edges=False,
                show_layer_labels=True, show_legend=False, tile_surroundings=False, font_size=8,
            ))
            fig.suptitle(
                f"{title}\nCrossings {drawing['geometric_crossings']}   |   "
                f"Bends {drawing['bends']}   |   Dummy vertices {ranking['predicted_dummies']}",
                fontsize=13,
            )
            with BytesIO() as buffer:
                fig.savefig(buffer, format="png", dpi=160, facecolor="white")
                buffer.seek(0)
                panels.append(Image.open(buffer).convert("RGB"))
            plt.close(fig)
        w, h = panels[0].size
        comparison = Image.new("RGB", (w * 2 + 10, h), "#dde6e8")
        comparison.paste(panels[0], (0, 0))
        comparison.paste(panels[1], (w + 10, 0))
        comparison.save(args.output / f"{case}.png")
        print(f"{case}: drawing and saved metrics agree")


if __name__ == "__main__":
    main()
