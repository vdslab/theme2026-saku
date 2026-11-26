"""Report the terminal outcome of each allocation and drawing path."""

import argparse
import csv
import json
from pathlib import Path


def terminal_stage(row, default):
    if row["status"] == "ok":
        return default
    if events := row.get("layout_stages"):
        return events[-1]["phase"]
    return default


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    args = parser.parse_args()

    cases = {}
    for line in args.rows.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        cases.setdefault(row["case"], {})[row["variant"]] = row

    fields = ("case", "family", "nodes", "edges", "allocation", "stage", "status")
    with args.rows.with_name("terminal_stages.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for case, variants in cases.items():
            setup = variants["setup_configuration"]
            common = {field: setup[field] for field in fields[:4]}
            for allocation in ("linear", "epigraph"):
                stages = (
                    ("configuration", setup),
                    ("allocation", variants.get(allocation)),
                    ("pipeline", variants.get(f"{allocation}_default_pipeline")),
                    ("geometry", variants.get(f"{allocation}_geometry")),
                )
                for default, row in stages:
                    if row is None:
                        raise ValueError(f"Missing {default} row for {case}, {allocation}")
                    if row["status"] != "ok" or default == "geometry":
                        writer.writerow({
                            **common,
                            "allocation": allocation,
                            "stage": terminal_stage(row, default),
                            "status": row["status"],
                        })
                        break


if __name__ == "__main__":
    main()
