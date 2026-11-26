"""Tabulate same-input changes from zero to one sifting pass."""

import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    args = parser.parse_args()
    cases = {}
    with args.rows.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            cases.setdefault(row["case"], {})[row["variant"]] = row

    metrics = ("crossings", "geometric_crossings", "bends", "either_seam_edges",
               "x_seam_edges", "y_seam_edges")
    columns = ["case", "seed", "layer_width", "layers", "sifting_seconds"]
    columns.extend(f"{metric}_{suffix}" for metric in metrics for suffix in ("0", "1", "delta"))
    with args.rows.with_name("width_pairs.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        for case, variants in cases.items():
            comparison = {}
            for rounds in (0, 1):
                variant = f"global_rounds_{rounds}"
                layout = variants[variant]
                geometry = variants[variant + "_geometry"]
                if layout["status"] != "ok" or geometry["status"] != "ok":
                    raise ValueError(f"Incomplete width comparison for {case}, {variant}")
                comparison[rounds] = {**geometry, **layout}
            after = comparison[1]
            record = {field: after[field] for field in columns[:4]}
            record["sifting_seconds"] = sum(
                stage["seconds"] for stage in after["layout_stages"] if stage["phase"] == "sift_blocks"
            )
            for metric in metrics:
                before_value, after_value = comparison[0][metric], after[metric]
                record.update({f"{metric}_0": before_value, f"{metric}_1": after_value,
                               f"{metric}_delta": after_value - before_value})
            writer.writerow(record)


if __name__ == "__main__":
    main()
