"""Verify saved cycle packings and summarize wrap-count intervals."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    with (args.run / "inputs.jsonl").open(encoding="utf-8") as source:
        inputs = {row["id"]: row for row in map(json.loads, source)}
    cases = defaultdict(dict)
    with (args.run / "rows.jsonl").open(encoding="utf-8") as source:
        for row in map(json.loads, source):
            cases[row["case"]][row["variant"]] = row
    if cases.keys() != inputs.keys():
        raise ValueError("Incomplete or unexpected trial coverage")

    summary = []
    for case, variants in cases.items():
        graph = inputs[case]["graph"]
        edges = set(map(tuple, graph["edges"]))
        initial_packing = variants["cycle_packing"]
        packings = [initial_packing]
        if "short_cycle_packing" in variants:
            packings.append(variants["short_cycle_packing"])
        for packing in packings:
            used = set()
            if "lower_bound" not in packing:
                continue
            assert packing["lower_bound"] == len(packing["cycles"])
            for cycle in packing["cycles"]:
                arcs = [tuple(arc) for arc in cycle]
                assert arcs and all(v == w for (_, v), (w, _) in zip(arcs, arcs[1:] + arcs[:1]))
                distinct = set(arcs)
                assert len(distinct) == len(arcs) and distinct <= edges - used
                used.update(distinct)
        packing = max(packings, key=lambda row: row.get("lower_bound", -1))
        lower = packing.get("lower_bound")
        initial = variants["feasible_order"]
        final = variants.get("insertion_refinement", initial)
        upper = final.get("upper_bound")
        if upper is not None:
            assert final["assignment_violations"] == 0
            assert lower is None or lower <= upper <= initial["upper_bound"]
        reference = variants.get("gurobi_reference", {})
        summary.append({
            "case": case, "family": inputs[case]["family"],
            "nodes": len(graph["nodes"]), "edges": len(edges),
            "lower_status": packing["status"], "lower_bound": lower,
            "initial_lower": initial_packing.get("lower_bound"),
            "initial_upper": initial.get("upper_bound"),
            "upper_status": final["status"], "upper_bound": upper,
            "gap": upper - lower if upper is not None and lower is not None else None,
            "layers_for_chosen_wraps": final.get("layers"),
            "reference_wraps": reference.get("reference_wraps"),
            "reference_limited": reference.get("solver_limited"),
            "square_status": variants.get("square_cut", {}).get("status"),
            "rounds0_status": variants.get("wrap_bounds_rounds_0", {}).get("status"),
            "rounds5_status": variants.get("wrap_bounds_rounds_5", {}).get("status"),
        })
    with (args.run / "bounds.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


if __name__ == "__main__":
    main()
