"""Summarize matched crossings without pooling overlapping neighborhoods as replicates."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from statistics import median


def summarize(rows):
    cases = defaultdict(dict)
    for row in rows:
        cases[row["family"], row["case"]][row["variant"]] = row
    by_family = defaultdict(list)
    for (family, _), variants in cases.items():
        by_family[family].append(variants)
    for family, cases in sorted(by_family.items()):
        statuses = Counter(case["torus"]["status"] for case in cases)
        deltas = [
            case["torus"]["geometric_crossings"] - case["dot"]["geometric_crossings"]
            for case in cases if case["torus"]["status"] == case["dot"]["status"] == "ok"
        ]
        yield {
            "network": family,
            "attempted": len(cases),
            "paired": len(deltas),
            "torus_status": json.dumps(dict(sorted(statuses.items()))),
            "fewer": sum(delta < 0 for delta in deltas),
            "equal": deltas.count(0),
            "more": sum(delta > 0 for delta in deltas),
            "median_delta": median(deltas) if deltas else None,
            "min_delta": min(deltas, default=None),
            "max_delta": max(deltas, default=None),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.rows.open() as source:
        results = list(summarize(map(json.loads, source)))
    with args.output.open("x", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    main()
