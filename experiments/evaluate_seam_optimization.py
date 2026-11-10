"""Reproducible before/after seam evaluation using the actual layout pipeline.

Run from the repository root with PYTHONPATH=src and the project interpreter.
Uses the application's configured Gurobi environment by default. --local-license
explicitly selects Gurobi's local environment for this experiment only.
"""

import argparse
import csv
from contextlib import ExitStack
from dataclasses import replace
import importlib
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from generator import generate_graph
from torus_layout import Graph
from torus_layout.coordinates import assign_coordinates
from torus_layout.crossing import count_crossings, count_seam_segments, optimize_seam
from torus_layout.drawing import DrawingOptions, draw_layout
from torus_layout.models import PipelineConfig
from torus_layout.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=int, nargs="+", default=[12, 25, 50])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--output", type=Path, default=Path("experiments/results/seam_optimization"))
    parser.add_argument("--local-license", action="store_true",
                        help="explicitly use local Gurobi license, as in solver tests")
    parser.add_argument("--coordinate-method", choices=["torus_qp", "torus_lp", "brandes_koepf"],
                        default="torus_qp")
    args = parser.parse_args()
    with ExitStack() as stack:
        if args.local_license:
            import gurobipy as gp

            def local_environment(verbose: bool = False) -> gp.Env:
                environment = gp.Env(params={"OutputFlag": int(verbose)})
                stack.callback(environment.dispose)
                return environment

            for name in (
                "torus_layout.layering.minimize_wraps",
                "torus_layout.layering.balance.diff",
                "torus_layout.layering.balance.diff_square",
                "torus_layout.layering.balance.qp",
                "torus_layout.coordinates.optimization",
            ):
                stack.enter_context(patch.object(importlib.import_module(name),
                                                "create_gurobi_env", local_environment))
        evaluate(args)


def evaluate(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    saved = False
    config = PipelineConfig(rounds=3, optimize_seams=False,
                            coordinate_method=args.coordinate_method)
    for n in args.nodes:
        for seed in args.seeds:
            nodes, edges, used_seed = generate_graph("cyclic", n=n, num_cycles=2, edge_prob=0.01, seed=seed)
            baseline = run_pipeline(Graph(tuple(nodes), tuple(edges)), config)
            if baseline is None:
                raise RuntimeError(f"layer assignment failed: n={n}, seed={seed}")
            started = perf_counter()
            after = optimize_seam(baseline.subdivided, baseline.crossing)
            elapsed = perf_counter() - started
            before_count = count_seam_segments(baseline.subdivided, baseline.crossing)
            after_count = count_seam_segments(baseline.subdivided, after)
            before_crossings = count_crossings(baseline.subdivided, baseline.crossing)
            after_crossings = count_crossings(baseline.subdivided, after)
            if after_count > before_count or after_crossings != before_crossings:
                raise AssertionError("seam count increased or embedding crossings changed")
            coordinates = assign_coordinates(
                baseline.subdivided, after, method=config.coordinate_method,
                bend_weight=config.coordinate_bend_weight,
            )
            # Repeat the public default path end-to-end for the first improved case.
            if after_count < before_count and not saved:
                integrated = run_pipeline(baseline.original_graph, replace(config, optimize_seams=True))
                if integrated is None:
                    raise AssertionError("integrated pipeline failed")
                if count_seam_segments(integrated.subdivided, integrated.crossing) != after_count:
                    raise AssertionError("integrated pipeline differs from postprocessing")
                saved = True
            if after_count < before_count:
                options = DrawingOptions(dpi=120)
                for name, crossing, positions in (
                    ("before", baseline.crossing, baseline.coordinates),
                    ("after", after, coordinates),
                ):
                    draw_layout(
                        baseline.subdivided, crossing, positions, options=options,
                        save_path=args.output / f"n{n}_seed{seed}_{name}.png", show=False,
                    )
            row = {
                "nodes": n, "seed": used_seed, "original_edges": len(edges),
                "subdivided_nodes": len(baseline.subdivided.graph.nodes),
                "segments": len(baseline.subdivided.graph.edges),
                "layers": len(baseline.crossing.order),
                "max_layer_size": max(map(len, baseline.crossing.order.values())),
                "seams_before": before_count, "seams_after": after_count,
                "crossings_before": before_crossings, "crossings_after": after_crossings,
                "seam_seconds": elapsed,
            }
            rows.append(row)
            # Persist completed cases even if a later solver run fails.
            with (args.output / "results.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader()
                writer.writerows(rows)
            print(json.dumps(row), flush=True)
    before = sum(row["seams_before"] for row in rows)
    after = sum(row["seams_after"] for row in rows)
    summary = {
        "cases": len(rows), "improved_cases": sum(r["seams_after"] < r["seams_before"] for r in rows),
        "seams_before": before, "seams_after": after,
        "reduction_fraction": (before - after) / before if before else 0,
        "all_crossings_preserved": True,
        "coordinate_method": config.coordinate_method,
        "rounds": config.rounds, "edge_probability": 0.01,
        "license_mode": "local" if args.local_license else "application_env",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    if not saved:
        raise AssertionError("no improved case found; expand evaluation inputs")


if __name__ == "__main__":
    main()
