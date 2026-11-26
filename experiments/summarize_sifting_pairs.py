"""Summarize matched sifting measurements, retaining failed inputs in denominators."""

import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import median

METRICS = ("crossings", "geometric_crossings", "type2", "bends", "y_seam_events", "seconds")


def summarize(rows):
    by_scope = defaultdict(dict)
    for row in rows:
        for scope in ("all", row["family"]):
            by_scope[scope].setdefault(row["case"], {})[row["method"]] = row

    for scope, inputs in sorted(by_scope.items()):
        pairs = [
            (methods["global"], methods["radial"])
            for methods in inputs.values()
            if all(methods.get(method, {}).get("status") == "ok" for method in ("global", "radial"))
        ]
        for metric in METRICS:
            differences = [float(left[metric]) - float(right[metric]) for left, right in pairs]
            yield {
                "scope": scope, "metric": metric, "attempted": len(inputs),
                "paired": len(pairs), "fewer": sum(delta < 0 for delta in differences),
                "tied": sum(delta == 0 for delta in differences),
                "more": sum(delta > 0 for delta in differences),
                "median_delta": median(differences) if differences else None,
                "min_delta": min(differences, default=None),
                "max_delta": max(differences, default=None),
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.measurements.open(newline="", encoding="utf-8") as source:
        rows = list(summarize(csv.DictReader(source)))
    if not rows:
        parser.error("no measurements to summarize")
    with args.output.open("x", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
