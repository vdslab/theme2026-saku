"""Backfill span histograms and the input-by-stage completion table."""

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from run_torus_study import ROOT
sys.path.insert(0, str(ROOT / "src"))

from torus_layout.layering import balance_layers
from torus_layout.models import Graph
from torus_study.stages import record_solver


def percentile95(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(.95 * len(ordered)) - 1)]


def main(folder):
    import argparse
    import gurobipy as gp
    args = argparse.Namespace(local_license=True, solver_seconds=4.0)
    folder = Path(folder)
    inputs = [json.loads(line) for line in (folder / "inputs.jsonl").read_text().splitlines()]
    rows = [json.loads(line) for line in (folder / "rows.jsonl").read_text().splitlines()]
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case"]][(row["stage"], row.get("method"))] = row
    profiles = []
    for item in inputs:
        group = by_case[item["case"]]
        search = group.get(("search", None), {})
        if search.get("status") != "ok":
            continue
        graph = Graph(tuple(range(item["nodes"])), tuple(map(tuple, item["edge_list"])))
        for variant, method in (("linear", "diff"), ("square", "diff_square")):
            old = group.get(("assignment", variant), {})
            if old.get("status") != "ok":
                continue
            trace = []
            with record_solver(args, trace):
                assignment = balance_layers(graph, search["wraps"], search["layers"], method)
            if not assignment.node_to_layer:
                continue
            spans = [assignment.node_to_layer[v] - assignment.node_to_layer[u]
                     + search["layers"] * int(assignment.torus_flags[u, v]) for u, v in graph.edges]
            profile = dict(sorted(Counter(spans).items()))
            profiles.append({"case": item["case"], "family": item["family"],
                             "nodes": item["nodes"], "edges": item["edges"],
                             "method": variant, "status": "ok",
                             "replay_optimality_status": "optimal" if trace and trace[-1]["status"] == gp.GRB.OPTIMAL else "feasible_not_proven_optimal",
                             "span_p95": percentile95(spans), "max_span": max(spans),
                             "span_sum": sum(spans), "span_square_sum": sum(x*x for x in spans),
                             "dummy_count_predicted": sum(x-1 for x in spans),
                             "span_frequency": json.dumps(profile, separators=(",", ":")),
                             "replay_seconds": trace[-1]["seconds"] if trace else None,
                             "objective": trace[-1].get("objective") if trace else None,
                             "bound": trace[-1].get("bound") if trace else None,
                             "relative_gap": abs(trace[-1]["objective"]-trace[-1]["bound"])/max(abs(trace[-1]["objective"]),1e-12) if trace and "objective" in trace[-1] and "bound" in trace[-1] else None})
    with (folder/"span_profiles.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(profiles[0]) if profiles else ["case"])
        writer.writeheader(); writer.writerows(profiles)

    # Consolidated run state makes it possible to see where each input stopped.
    completion = []
    for item in inputs:
        group = by_case[item["case"]]
        row = {"case": item["case"], "family": item["family"], "nodes": item["nodes"],
               "edges": item["edges"], "seed": item["seed"]}
        for stage, method, label in (("search", None, "search"),
                                     ("assignment", "linear", "linear_assignment"),
                                     ("assignment", "square", "square_assignment"),
                                     ("drawing", "linear", "linear_drawing"),
                                     ("drawing", "square", "square_drawing")):
            record = group.get((stage, method), {})
            row[label+"_status"] = record.get("status", "not_reached")
            if label == "search" and record.get("status") == "ok":
                row["layers"], row["wraps"] = record.get("layers"), record.get("wraps")
            if label in ("linear_assignment", "square_assignment") and record:
                row[label+"_solver_status"] = record.get("optimality_status")
                trace = record.get("solver") or []
                if trace:
                    row[label+"_objective"] = trace[-1].get("objective")
                    row[label+"_bound"] = trace[-1].get("bound")
                    row[label+"_gap"] = trace[-1].get("relative_gap")
            if label in ("linear_drawing", "square_drawing"):
                row[label+"_fallback"] = record.get("coordinate_fallback")
        completion.append(row)
    with (folder/"input_completion.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(completion[0]))
        writer.writeheader(); writer.writerows(completion)

    # Add p95 comparisons and profile-comparable counts to the size/family summary.
    pmap = {(p["case"], p["method"]): p for p in profiles}
    paired = list(csv.DictReader((folder/"paired.csv").open(encoding="utf-8")))
    by_group = defaultdict(list)
    for row in paired:
        l = pmap.get((row["case"], "linear")); s = pmap.get((row["case"], "square"))
        if l and s:
            by_group[(int(row["nodes"]),row["family"])].append(s["span_p95"]-l["span_p95"])
    with (folder/"summary.csv").open(encoding="utf-8") as f:
        original=list(csv.DictReader(f))
        fields=list(original[0])+["span_p95_comparable","span_p95_diff_median","span_p95_decrease","span_p95_same","span_p95_increase"]
    for row in original:
        diffs=by_group.get((int(row["nodes"]),row["family"]),[])
        ordered=sorted(diffs)
        row["span_p95_comparable"]=len(diffs)
        row["span_p95_diff_median"]=(ordered[len(ordered)//2] if len(ordered)%2 else (ordered[len(ordered)//2-1]+ordered[len(ordered)//2])/2) if ordered else ""
        row["span_p95_decrease"]=sum(x<0 for x in diffs)
        row["span_p95_same"]=sum(x==0 for x in diffs)
        row["span_p95_increase"]=sum(x>0 for x in diffs)
    with (folder/"summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(original)


if __name__ == "__main__":
    main(sys.argv[1])
