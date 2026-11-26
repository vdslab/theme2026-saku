"""Measure how a change in orientation alters the torus–dot crossing difference."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from random import Random
from statistics import median


def summarize(source):
    blocks = defaultdict(dict)
    for row in source:
        blocks[row["block"]][row["orientation"], row["variant"]] = row

    def difference(rows, orientation):
        pair = [rows.get((orientation, method), {}) for method in ("torus", "dot")]
        if all(row.get("status") == "ok" for row in pair):
            return pair[0]["geometric_crossings"] - pair[1]["geometric_crossings"]
        return None

    for block, rows in sorted(blocks.items()):
        coherent = difference(rows, "coherent")
        for orientation in sorted({direction for direction, _ in rows}):
            value = difference(rows, orientation)
            yield {
                "block": block, "orientation": orientation,
                "torus_minus_dot": value,
                "change_from_coherent": None if value is None or coherent is None else value - coherent,
            }


def summarize_changes(groups):
    rng = Random(20261126)
    for orientation, rows in groups.items():
        changes = [row["change_from_coherent"] for row in rows
                   if row["change_from_coherent"] is not None]
        interval = sorted(median(rng.choices(changes, k=len(changes))) for _ in range(4000)) if changes else []
        yield {
            "orientation": orientation, "blocks": len(rows), "paired": len(changes),
            "increased": sum(change > 0 for change in changes),
            "unchanged": sum(change == 0 for change in changes),
            "decreased": sum(change < 0 for change in changes),
            "median_change": median(changes) if changes else None,
            "bootstrap_low": interval[99] if interval else None,
            "bootstrap_high": interval[3899] if interval else None,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.rows.open(encoding="utf-8") as handle:
        rows = list(summarize(json.loads(line) for line in handle))
    if not rows:
        parser.error("no measurements to summarize")

    args.output.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    for row in rows:
        groups[row["orientation"]].append(row)
    for filename, records in (
        ("orientation_pairs.csv", rows),
        ("orientation_summary.csv", list(summarize_changes(groups))),
    ):
        with (args.output / filename).open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=records[0])
            writer.writeheader()
            writer.writerows(records)

    from matplotlib import pyplot as plt

    figure, axes = plt.subplots(figsize=(6, 3.1), layout="constrained")
    for index, group in enumerate(groups.values()):
        comparable = sorted(row["torus_minus_dot"] for row in group if row["torus_minus_dot"] is not None)
        axes.scatter(comparable, [index] * len(comparable), alpha=.4, s=18, color="#255ba8")
        if comparable:
            axes.scatter(median(comparable), index, marker="D", s=35, color="#143754")
        axes.text(1.02, index, f"{len(comparable)}/{len(group)}",
                  transform=axes.get_yaxis_transform(), ha="left", va="center", fontsize=9)
    axes.axvline(0, color="#999999", linewidth=1)
    axes.set_yticks(range(len(groups)), [key.replace("_", " ") for key in groups])
    axes.set_xlabel("Geometric crossings (torus − dot)")
    figure.savefig(args.output / "orientation_pairs.pdf")
    figure.savefig(args.output / "orientation_pairs.png", dpi=180)


if __name__ == "__main__":
    main()
