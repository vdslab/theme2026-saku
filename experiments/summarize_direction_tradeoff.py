"""Aggregate paired Torus/dot quality metrics by input family."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from statistics import median


DIFFERENCES = ("geometric_crossings", "bends", "overlapping_edge_pairs",
               "length_per_frame_diagonal")


def summarize(rows):
    cases = defaultdict(dict)
    for row in rows:
        if row["variant"] in ("torus", "dot"):
            cases[row["family"], row["case"]][row["variant"]] = row
    by_family = defaultdict(list)
    for (family, _), variants in cases.items():
        by_family[family].append(variants)
    for family, cases in sorted(by_family.items()):
        pairs = [(case["torus"], case["dot"]) for case in cases
                 if case["torus"]["status"] == case["dot"]["status"] == "ok"]
        result = {"family": family, "attempted": len(cases), "pairs": len(pairs)}
        if pairs:
            for metric in DIFFERENCES:
                delta = [torus[metric] - dot[metric] for torus, dot in pairs]
                result[f"{metric}_median_delta"] = median(delta)
                result[f"{metric}_fewer"] = sum(d < 0 for d in delta)
                result[f"{metric}_more"] = sum(d > 0 for d in delta)
            result.update({
                "torus_reverse_edges_total": sum(torus["reverse_direction_edges"] for torus, _ in pairs),
                "dot_reverse_fraction_median": median(dot["reverse_direction_edges"] / dot["edges"]
                                                     for _, dot in pairs),
                "torus_x_seam_edge_fraction_median": median(torus["x_seam_edges"] / torus["edges"]
                                                          for torus, _ in pairs),
                "torus_either_seam_edge_fraction_median": median(torus["either_seam_edges"] / torus["edges"]
                                                               for torus, _ in pairs),
            })
        yield result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.rows.open(encoding="utf-8") as source:
        rows = list(summarize(map(json.loads, source)))
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with args.output.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
