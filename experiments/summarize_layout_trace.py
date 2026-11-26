"""Flatten completed and interrupted pipeline calls for stage-level analysis."""

import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    args = parser.parse_args()
    fields = ("case", "variant", "status", "nodes", "edges", "step", "phase",
              "complete", "seconds", "seam_method", "segments", "dummy_nodes")
    with args.rows.open(encoding="utf-8") as source, args.rows.with_name("layout_stages.csv").open(
        "x", encoding="utf-8", newline=""
    ) as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for line in source:
            row = json.loads(line)
            common = {key: row[key] for key in fields[:5]}
            for step, event in enumerate(row.get("layout_stages", []), 1):
                writer.writerow({**common, "step": step, **event})


if __name__ == "__main__":
    main()
