"""Plot time and drawing-quality changes for paired layer assignments."""

import argparse
import csv
from pathlib import Path

from matplotlib import pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.pairs.open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    widths = sorted({int(row["layer_width"]) for row in rows})
    seeds = sorted({row["seed"] for row in rows})
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.3), layout="constrained")
    measures = (
        ("sifting_seconds", "Sifting time (s)", 1),
        ("geometric_crossings_delta", "Crossings removed", -1),
        ("either_seam_edges_delta", "Additional boundary-crossing edges", 1),
    )
    for ax, (field, label, sign) in zip(axes, measures, strict=True):
        for seed, color, marker in zip(seeds, ("#176690", "#b74c28", "#387543"),
                                       ("o", "s", "^"), strict=True):
            by_width = {int(row["layer_width"]): float(row[field])
                        for row in rows if row["seed"] == seed}
            ax.plot(widths, [sign * by_width[w] for w in widths], color=color,
                    marker=marker, markerfacecolor="white", label=f"Seed {seed}", linewidth=1.5)
        ax.set(xlabel="Vertices per layer", ylabel=label, xticks=widths, ylim=(0, None))
        ax.grid(axis="y", color="#dddddd", linewidth=.7)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncols=3, frameon=False)
    fig.savefig(args.output)
    fig.savefig(args.output.with_suffix(".png"), dpi=180)


if __name__ == "__main__":
    main()
