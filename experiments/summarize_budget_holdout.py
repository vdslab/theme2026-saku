"""Summarize paired quality metrics on the independent budget-validation inputs."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--dot-run", type=Path)
    args = parser.parse_args()
    with (args.run / "inputs.jsonl").open() as source:
        inputs = {row["id"]: row for row in map(json.loads, source)}
    variants = defaultdict(dict)
    with (args.run / "rows.jsonl").open() as source:
        for row in map(json.loads, source):
            variants[row["case"]][row["variant"]] = row
    assert inputs.keys() == variants.keys()
    dot = {}
    if args.dot_run is not None:
        with (args.dot_run / "inputs.jsonl").open() as source:
            reference = {row["id"]: row for row in map(json.loads, source)}
        assert reference.keys() == inputs.keys()
        assert all(reference[case]["graph"] == inputs[case]["graph"] for case in inputs)
        with (args.dot_run / "rows.jsonl").open() as source:
            dot = {row["case"]: row for row in map(json.loads, source) if row["variant"] == "dot_geometry"}

    records = []
    for case, manifest in inputs.items():
        trial = variants[case]
        row = {field: manifest[field] for field in ("family", "nodes", "edges", "seed")}
        row["case"] = case
        for budget in (0, 20):
            layout = trial.get(f"torus_budget_{budget}", {})
            geometry = trial.get(f"torus_budget_{budget}_geometry", {})
            row.update({
                f"layout_{budget}": layout.get("status", "not_started"),
                f"geometry_{budget}": geometry.get("status", "not_started"),
                f"downstream_seconds_{budget}": layout.get("wall_seconds"),
                f"crossings_{budget}": geometry.get("geometric_crossings"),
                f"bends_{budget}": geometry.get("bends"),
                f"seam_edges_{budget}": geometry.get("either_seam_edges"),
                f"cutoff_{budget}": layout.get("sifting_cutoff"),
            })
        pair = row["geometry_0"] == row["geometry_20"] == "ok"
        for metric in ("crossings", "bends", "seam_edges"):
            row[f"{metric}_change"] = row[f"{metric}_20"] - row[f"{metric}_0"] if pair else None
        if args.dot_run is not None:
            reference = dot.get(case, {})
            row.update({"dot_geometry": reference.get("status", "not_started"),
                        "dot_crossings": reference.get("geometric_crossings"),
                        "dot_bends": reference.get("bends")})
            row["crossings_20_minus_dot"] = (
                row["crossings_20"] - row["dot_crossings"]
                if row["geometry_20"] == row["dot_geometry"] == "ok" else None
            )
        records.append(row)

    filename = "pairs.csv" if args.dot_run is None else "pairs_with_dot.csv"
    with (args.run / filename).open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    groups = defaultdict(list)
    for row in records:
        groups[row["family"]].append(row)
    for family, rows in groups.items():
        paired = [r for r in rows if r["crossings_change"] is not None]
        delta = [r["crossings_change"] for r in paired]
        summary = {
            "family": family, "attempted": len(rows), "paired": len(paired),
            "fewer": sum(value < 0 for value in delta),
            "equal": delta.count(0), "more": sum(value > 0 for value in delta),
            "median_change": median(delta) if delta else None,
            "median_relative_change": median(r["crossings_change"] / r["crossings_0"] for r in paired
                                             if r["crossings_0"]) if any(r["crossings_0"] for r in paired) else None,
        }
        if args.dot_run is not None:
            deltas = [r["crossings_20_minus_dot"] for r in rows if r["crossings_20_minus_dot"] is not None]
            summary.update(dot_pairs=len(deltas), fewer_than_dot=sum(value < 0 for value in deltas),
                           equal_to_dot=deltas.count(0), more_than_dot=sum(value > 0 for value in deltas),
                           median_difference_from_dot=median(deltas) if deltas else None)
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
