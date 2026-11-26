"""Render the non-overlapping sifting phase totals from a profile JSONL."""

import argparse
import csv
import json
from pathlib import Path

from matplotlib import pyplot as plt


LABELS = {
    "integer": "Integer scoring",
    "vector": "Vectorized parting",
    "vector_cached": "Reuse strip scores",
    "vector_incremental": "Update changed layer orders",
    "vector_delta": "Update changed strip totals",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    rows = {}
    for filename in ("profile.jsonl", "incremental_profile.jsonl", "delta_profile.jsonl"):
        with (args.run / filename).open(encoding="utf-8") as source:
            for row in map(json.loads, source):
                rows.setdefault(row["mode"], row)
    summary = []
    for name, label in LABELS.items():
        row = rows[name]
        functions = {f["function"]: f for f in row["functions"]}
        score = functions["_strip_score"]["cumulative_seconds"]
        order = functions["_trial_orders"]["cumulative_seconds"]
        total = functions["sift_blocks"]["cumulative_seconds"]
        summary.append({"mode": name, "label": label, "checks": row["checks"],
                        "scorer_calls": functions["_strip_score"]["calls"],
                        "score_seconds": score, "order_seconds": order,
                        "other_seconds": total - score - order, "total_seconds": total})
    with (args.run / "profile_summary.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    fig, ax = plt.subplots(figsize=(7.8, 3.1), layout="constrained")
    start = [0.] * len(summary)
    for column, label, color in (
        ("score_seconds", "Strip scoring", "#255787"),
        ("order_seconds", "Candidate layer orders", "#d9703f"),
        ("other_seconds", "Other sifting work", "#abb3bc"),
    ):
        values = [row[column] for row in summary]
        ax.barh([row["label"] for row in summary], values, left=start, label=label, color=color)
        start = [x + y for x, y in zip(start, values, strict=True)]
    ax.invert_yaxis()
    ax.set_xlabel("Cumulative profiler time (s)")
    ax.set_title("First 3,000 stop checks on the same 500-vertex input", loc="left", fontsize=10)
    ax.legend(loc="lower right", frameon=False)
    fig.savefig(args.run / "profile_phases.pdf")
    fig.savefig(args.run / "profile_phases.png", dpi=180)


if __name__ == "__main__":
    main()
