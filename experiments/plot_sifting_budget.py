"""Summarize and plot matched sifting-budget trials."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

from matplotlib import pyplot as plt


def summarize(source):
    cases = defaultdict(dict)
    for row in source:
        cases[row["case"]][row["variant"]] = row
    for case, variants in sorted(cases.items()):
        layout_rows = [row for row in variants.values() if "sifting_budget_seconds" in row]
        for row in sorted(layout_rows, key=lambda item: item["sifting_budget_seconds"]):
            geometry = variants.get(row["variant"] + "_geometry", {})
            yield {
                "case": case, "vertices": row["nodes"],
                "seconds_budget": row["sifting_budget_seconds"],
                "layout_status": row["status"], "geometry_status": geometry.get("status"),
                "cutoff": row["sifting_cutoff"], "stop_checks": row["sifting_stop_checks"],
                "downstream_seconds": row["wall_seconds"],
                "geometry_seconds": geometry.get("wall_seconds"),
                "geometric_crossings": geometry.get("geometric_crossings"),
                "bends": geometry.get("bends"),
                "edges_crossing_either_seam": geometry.get("either_seam_edges"),
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    with (args.run / "rows.jsonl").open(encoding="utf-8") as source:
        rows = list(summarize(map(json.loads, source)))
    with (args.run / "budget_summary.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    groups = defaultdict(list)
    for row in rows:
        groups[row["case"]].append(row)
    figure, axes = plt.subplots(1, len(groups), figsize=(7.5, 3.1), squeeze=False,
                                layout="constrained")
    ordered_groups = sorted(groups.values(), key=lambda group: group[0]["vertices"])
    for ax, group in zip(axes[0], ordered_groups, strict=True):
        values = [row["geometric_crossings"] for row in group]
        ax.plot([row["seconds_budget"] for row in group], values, "o-",
                color="#21578e", linewidth=1.6)
        ax.set_title(f'{group[0]["vertices"]:,} vertices')
        ax.set_xlabel("Sifting budget per call (s)")
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.grid(axis="y", color="#dddddd", linewidth=.7)
    axes[0][0].set_ylabel("Geometric crossings")
    figure.savefig(args.run / "budget_crossings.pdf")
    figure.savefig(args.run / "budget_crossings.png", dpi=180)


if __name__ == "__main__":
    main()
