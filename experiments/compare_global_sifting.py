"""Compare the two torus sifting methods on identical layered inputs."""

import argparse
from collections.abc import Callable
import csv
from itertools import combinations, product
from pathlib import Path
from random import Random
from statistics import median
import sys
from time import perf_counter
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from generator.watts_strogatz import generate_watts_strogatz_graph
from torus_layout.coordinates import assign_coordinates
from torus_layout.crossing import count_crossings, reduce_crossings
from torus_layout.crossing.lib.crossings import crossings_between_edges, pair_positions
from torus_layout.crossing.lib.embedding import edges_by_directed_strip
from torus_layout.drawing import DrawingOptions, draw_layout
from torus_layout.layering.router import assign_layers
from torus_layout.models import Graph
from torus_layout.reporting import boundary_metrics
from torus_layout.subdivision import insert_dummy_nodes
from torus_study.geometry import crossing_metrics, route_metrics, torus_routes, turns
from torus_study.stages import assignment_metrics, coordinate_metrics, record_solver, subdivision_metrics
from torus_study.validation_inputs import public_trials


def cases():
    for n, seed in product((12, 18, 24), (17, 42)):
        nodes, arcs = generate_watts_strogatz_graph(n, 4, .1, seed=seed)
        rng = Random(seed)
        rank = {node: value for value, node in enumerate(rng.sample(nodes, len(nodes)))}
        for family, edges in (
            ("ring", arcs),
            ("random", [(v, u) if rng.randrange(2) else (u, v) for u, v in arcs]),
            ("dag", [(v, u) if rank[u] > rank[v] else (u, v) for u, v in arcs]),
        ):
            yield f"ws-{n}-{seed}-{family}", family, Graph(tuple(nodes), tuple(edges))
    nodes, edges = generate_watts_strogatz_graph(30, 4, .1, seed=42)
    yield "ws-30-42-ring", "ring", Graph(tuple(nodes), tuple(edges))
    sources = ROOT / "output/torus_validation_20261120/sources"
    if all((sources / filename).is_file() for filename in ("sampson.zip", "UKfaculty.csv", "macaque.csv")):
        for trial in public_trials(sources):
            yield trial.case.id, "public", trial.case.graph


def inner_crossings(graph, crossing):
    dummy = graph.dummy_nodes
    edges = [edge for edge in graph.graph.edges if set(edge) <= dummy]
    layers = sorted(graph.layers)
    count = 0
    for pair, strip in edges_by_directed_strip(crossing.order, layers, edges).items():
        start, end = pair_positions(crossing.order, *pair)
        count += sum(crossings_between_edges(a, b, start, end, crossing.winding_numbers)
                     for a, b in combinations(strip, 2))
    return count


def evaluate(name, family, graph, *, repetitions=3, matched_postprocessing=False,
             coordinate_method="brandes_koepf_blocks_unsplit"):
    settings = SimpleNamespace(local_license=True, solver_seconds=3.0)
    solver_trace = []
    with record_solver(settings, solver_trace):
        assigned = assign_layers(graph)
    row = {"case": name, "family": family, "nodes": len(graph.nodes), "edges": len(graph.edges),
           "solver_limited": any(item["status"] not in (2, 3) for item in solver_trace),
           "coordinate_method": coordinate_method}
    if assigned is None:
        return [{**row, "status": "no_assignment"}], {}
    search, assignment = assigned
    stats = assignment_metrics(graph, assignment, search.layer_count, search.torus_count)
    if stats["assignment_violations"]:
        return [{**row, "status": "invalid_assignment"}], {}
    divided = insert_dummy_nodes(graph, assignment)
    paths, stats = subdivision_metrics(graph, divided)
    if stats["unit_span_violations"]:
        return [{**row, "status": "invalid_subdivision"}], {}

    outcomes = []
    drawings = {}
    # Alternate evaluation order across runs.
    methods = ("global", "radial") if name.endswith("-random") or "-42-" in name else ("radial", "global")
    timings = {method: [] for method in methods}
    results = {}
    for repetition in range(repetitions):
        for method in methods if repetition % 2 == 0 else reversed(methods):
            legacy_postprocessing = method == "radial" and not matched_postprocessing
            started = perf_counter()
            crossing = reduce_crossings(divided, rounds=5, sifting_method=method,
                                        unwind=legacy_postprocessing, algo2=legacy_postprocessing)
            timings[method].append(perf_counter() - started)
            results[method] = crossing
    for method in methods:
        crossing = results[method]
        elapsed = median(timings[method])
        conflict_count = inner_crossings(divided, crossing)
        if method == "global" and conflict_count:
            raise AssertionError(f"{name}: global sifting returned {conflict_count} type-2 conflicts")
        count = count_crossings(divided, crossing)
        boundary = boundary_metrics(divided, crossing.winding_numbers)
        embedding_row = {
            **row, "layers": len(divided.layers), "dummy_nodes": len(divided.dummy_nodes),
            "method": method, "seconds": elapsed, "repetitions": repetitions,
            "matched_postprocessing": matched_postprocessing,
            "crossings": count, "type2": conflict_count,
            "y_seam_segments": boundary["y_seam_segments"],
            "y_seam_events": boundary["y_seam_events"],
        }
        try:
            coordinates = assign_coordinates(divided, crossing, method=coordinate_method)
        except ValueError as error:
            outcomes.append({**embedding_row, "status": "coordinate_error", "error": str(error)})
            continue
        validation = coordinate_metrics(divided, crossing, coordinates)
        assert not any(value for key, value in validation.items() if key.endswith("violations"))
        routes, bounds = torus_routes(paths, divided, crossing, coordinates)
        drawn = route_metrics(routes, bounds)
        bends = {route.edge: turns(route.corners) for route in routes}
        selected = [route for route in routes if route.edge in ((6, 8), (6, 11))]
        selected_crossings = (crossing_metrics(selected, bounds)["geometric_crossings"]
                              if len(selected) == 2 else None)
        outcomes.append({
            **embedding_row, "status": "ok",
            "geometric_crossings": drawn["geometric_crossings"],
            "bends": drawn["bends"], "over_two_bends": sum(n > 2 for n in bends.values()),
            "total_edge_length": drawn["total_edge_length"],
            "edge_6_8_bends": bends.get((6, 8)), "edge_6_11_bends": bends.get((6, 11)),
            "edge_6_8_vs_6_11_crossings": selected_crossings,
        })
        drawings[method] = (divided, crossing, coordinates)
    return outcomes, drawings


def save_pair(output, rows, drawings, index):
    options = DrawingOptions(tile_surroundings=False, figsize=(13.5, 4.5), dpi=170)
    for method in ("radial", "global"):
        filename = output / f"example_{index}_{method}.png"
        draw_layout(*drawings[method], options=options, save_path=filename, show=False)
    save_pair_comparison(output, rows, index)


def save_pair_comparison(output, rows, index):
    from matplotlib import pyplot as plt
    from PIL import Image, ImageChops

    methods = ("radial", "global")
    images = {}
    for method in methods:
        filename = output / f"example_{index}_{method}.png"
        with Image.open(filename) as img:
            images[method] = img.convert("RGB")
    frames = [ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox()
              for img in images.values()]
    left, top, right, bottom = zip(*frames)
    crop = (min(left), min(top), max(right), max(bottom))
    tall = crop[2] - crop[0] < 1.4 * (crop[3] - crop[1])
    shape = (1, 2) if tall else (2, 1)
    fig, axes = plt.subplots(*shape, figsize=(10, 7.2), layout="constrained")
    for method, ax in zip(methods, axes, strict=True):
        ax.imshow(images[method].crop(crop))
        ax.set_axis_off()
        m = next(r for r in rows if r["method"] == method)
        ax.set_title(f"{method.capitalize()} sifting\n"
                     f"Crossings: {m['crossings']}  |  Type 2: {m['type2']}  |  Bends: {m['bends']}",
                     pad=4, fontsize=11, color="#182d30")
    fig.savefig(output / f"example_{index}.png", dpi=160, facecolor="white")
    plt.close(fig)


def save_witness(output, original, drawings):
    """Show the two edges discussed in the 30-node case on a shared scale."""
    from matplotlib import pyplot as plt

    highlighted = {(6, 8): "#0068b4", (6, 11): "#b64c22"}
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True, sharey=True,
                             layout="constrained")
    extents = []
    for method, ax in zip(("radial", "global"), axes, strict=True):
        graph, crossing, coordinates = drawings[method]
        chains, _ = subdivision_metrics(original, graph)
        routes, _ = torus_routes(chains, graph, crossing, coordinates)
        for route in routes:
            color = highlighted.get(route.edge, "#d9dedc")
            for start, end in route.pieces:
                ax.plot((start[0], end[0]), (start[1], end[1]), color=color,
                        linewidth=2.2 if route.edge in highlighted else .9,
                        zorder=2 if route.edge in highlighted else 1)
                if route.edge in highlighted:
                    extents.extend((start, end))
        for node in (6, 8, 11):
            x, y = coordinates.positions[node]
            ax.text(x, y, str(node), ha="center", va="center", fontsize=9, zorder=3,
                    bbox={"boxstyle": "circle,pad=.2", "facecolor": "white",
                          "edgecolor": "#566261"})
        ax.set_title(f"{method.capitalize()} sifting", loc="left")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("Layer")
        ax.set_ylabel("Vertical coordinate")
    xs, ys = zip(*extents)
    axes[0].set(xlim=(min(xs) - .5, max(xs) + .5), ylim=(min(ys) - .5, max(ys) + .5))
    fig.savefig(output / "witness_edges.png", dpi=160, facecolor="white")
    plt.close(fig)


def choose_examples(results, reader: Callable[[str], int]):
    focal = "ws-30-42-ring"
    candidates = [key for key, (rows, _) in results.items() if key != focal and rows[0]["family"] != "public"]
    examples = [focal] if focal in results else []
    if candidates:
        for key in (min(candidates, key=reader), max(candidates, key=reader)):
            if key not in examples:
                examples.append(key)
    public = [key for key, (rows, _) in results.items() if rows[0]["family"] == "public"]
    if public:
        examples.append(max(public, key=lambda key: abs(reader(key))))
    return examples


def save_crossing_deltas(output, results, delta: Callable[[str], int]):
    from matplotlib import pyplot as plt

    names = sorted(results, key=lambda key: (delta(key), key))
    values = [delta(key) for key in names]
    fig, ax = plt.subplots(figsize=(9, max(3, .26 * len(names) + 1.4)), layout="constrained")
    colors = ["#16766b" if value < 0 else "#9d462e" if value > 0 else "#586369" for value in values]
    ax.barh(names, values, color=colors)
    ax.scatter([0] * values.count(0), [name for name, value in zip(names, values) if value == 0],
               color="#586369", s=11, zorder=3)
    ax.invert_yaxis()
    ax.axvline(0, color="#586369", linewidth=.8)
    ax.set_xlabel("Difference in crossings (Global − Radial)")
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.savefig(output / "crossing_deltas.png", dpi=150, facecolor="white")
    plt.close(fig)


def write_csv(output, name, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (output / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--matched-postprocessing", action="store_true",
                        help="Disable Algo2 and UNWIND for both methods.")
    parser.add_argument("--coordinate-method",
                        choices=("brandes_koepf_blocks_unsplit", "brandes_koepf_blocks"),
                        default="brandes_koepf_blocks_unsplit")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    args.output.mkdir(parents=True, exist_ok=True)
    all_rows = []
    examples = {}
    for name, family, graph in cases():
        try:
            rows, drawings = evaluate(name, family, graph, repetitions=args.repetitions,
                                      matched_postprocessing=args.matched_postprocessing,
                                      coordinate_method=args.coordinate_method)
        except ValueError as error:
            rows = [{"case": name, "family": family, "nodes": len(graph.nodes),
                     "edges": len(graph.edges), "status": "failed", "error": str(error),
                     "coordinate_method": args.coordinate_method}]
            drawings = {}
        all_rows.extend(rows)
        write_csv(args.output, "measurements.csv", all_rows)
        if len(drawings) == 2:
            examples[name] = rows, drawings
            if name == "ws-30-42-ring":
                save_witness(args.output, graph, drawings)
        print(name, [r.get("crossings", r["status"]) for r in rows], flush=True)
    def crossing_delta(name):
        before, after = (next(r["crossings"] for r in examples[name][0] if r["method"] == method)
                         for method in ("radial", "global"))
        return after - before

    mapping = []
    for index, key in enumerate(choose_examples(examples, crossing_delta), 1):
        rows, drawings = examples[key]
        save_pair(args.output, rows, drawings, index)
        mapping.append({"figure": f"example_{index}.png", "case": key, "crossing_delta": crossing_delta(key)})
    write_csv(args.output, "examples.csv", mapping)
    if examples:
        save_crossing_deltas(args.output, examples, crossing_delta)


if __name__ == "__main__":
    main()
