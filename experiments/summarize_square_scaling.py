"""Pair rank-assignment objectives and report integer-bound certificates."""

import argparse
from collections import defaultdict
import csv
import json
from math import ceil
from pathlib import Path


def summarize(rows):
    inputs = defaultdict(dict)
    for row in rows:
        inputs[row["case"]][row["variant"]] = row

    for case, variants in inputs.items():
        setup = variants["setup_configuration"]
        linear = variants.get("linear", {})
        quadratic = variants.get("quadratic", {})
        epigraph = variants.get("epigraph", {})
        lhs = variants.get("linear_drawing_one_round", {})
        rhs = variants.get("epigraph_drawing_one_round", {})
        linear_pipeline = variants.get("linear_default_pipeline", {})
        square_pipeline = variants.get("epigraph_default_pipeline", {})
        linear_geometry = variants.get("linear_geometry", {})
        square_geometry = variants.get("epigraph_geometry", {})
        trace = epigraph.get("solver", [])
        bound = trace[-1].get("bound") if trace else None
        incumbent = epigraph.get("span_square_sum")
        lower = ceil(bound - 1e-6) if bound is not None else None
        yield {
            "case": case, "family": setup["family"], "nodes": setup["nodes"], "edges": setup["edges"],
            "setup_status": setup["status"], "setup_solver_limited": setup["solver_limited"],
            "linear_status": linear.get("status"),
            "linear_span_square_sum": linear.get("span_square_sum"),
            "quadratic_status": quadratic.get("status"),
            "quadratic_span_square_sum": quadratic.get("span_square_sum"),
            "epigraph_status": epigraph.get("status"),
            "epigraph_solve_seconds": epigraph.get("seconds"),
            "epigraph_span_square_sum": incumbent,
            "epigraph_integer_lower_bound": lower,
            "epigraph_integer_gap": incumbent - lower if incumbent is not None and lower is not None else None,
            "linear_drawing_status": lhs.get("status"),
            "linear_crossings": lhs.get("crossings"),
            "epigraph_drawing_status": rhs.get("status"),
            "epigraph_crossings": rhs.get("crossings"),
            "linear_pipeline_status": linear_pipeline.get("status"),
            "epigraph_pipeline_status": square_pipeline.get("status"),
            "linear_seam": linear_pipeline.get("seam_method_used"),
            "epigraph_seam": square_pipeline.get("seam_method_used"),
            "linear_pipeline_crossings": linear_pipeline.get("crossings"),
            "epigraph_pipeline_crossings": square_pipeline.get("crossings"),
            "linear_geometry_status": linear_geometry.get("status"),
            "epigraph_geometry_status": square_geometry.get("status"),
            "linear_geometric_crossings": linear_geometry.get("geometric_crossings"),
            "epigraph_geometric_crossings": square_geometry.get("geometric_crossings"),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    args = parser.parse_args()
    with args.rows.open(encoding="utf-8") as source:
        rows = list(summarize(map(json.loads, source)))
    with args.rows.with_name("objective_comparison.csv").open("x", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
