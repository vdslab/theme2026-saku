"""Plot the three measured layouts on each independent input."""

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
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.6), sharey=True, layout="constrained")
    for family, label, ax in (
        ("cycle", "Directed cycle with added arcs", axes[0]),
        ("watts_strogatz", "Watts–Strogatz", axes[1]),
    ):
        selected = [row for row in rows if row["family"] == family]
        for row in selected:
            values = [float(row[key]) if row[key] else None
                      for key in ("crossings_0", "crossings_20", "dot_crossings")]
            ax.plot(range(3), values, "o-", alpha=.65,
                    color="#225581" if int(row["nodes"]) == 90 else "#b34f20")
        ax.set_title(label)
        ax.set_xticks(range(3), ["Torus\n0 s", "Torus\n20 s", "dot"])
        ax.set_yscale("log")
        ax.grid(axis="y", color="#dddddd", linewidth=.7)
    axes[0].set_ylabel("Geometric crossings (log scale)")
    handles = [plt.Line2D([], [], color=color, label=f"{size} vertices")
               for size, color in ((90, "#225581"), (120, "#b34f20"))]
    fig.legend(handles=handles, loc="outside upper center", ncols=2, frameon=False)
    fig.savefig(args.output)
    fig.savefig(args.output.with_suffix(".png"), dpi=180)


if __name__ == "__main__":
    main()
