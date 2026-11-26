"""Plot measured and censored sifting times on fixed-rank graphs."""

import argparse
import json
from pathlib import Path

from matplotlib import pyplot as plt
from matplotlib.lines import Line2D


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.rows.open(encoding="utf-8") as source:
        rows = list(map(json.loads, source))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), sharey=True, layout="constrained")
    variants = (
        ("baseline", "Existing enumeration", "#18365f", -.035),
        ("sparse_candidates", "Distinct-order enumeration", "#b95428", .035),
    )
    for width, ax in zip((5, 10), axes, strict=True):
        for variant, _, color, shift in variants:
            for row in rows:
                if row["layer_width"] != width or row["variant"] != variant:
                    continue
                duration = next(e["seconds"] for e in row["layout_stages"]
                                if e["phase"] == "sift_blocks")
                timed_out = row["status"] == "wall_timeout"
                ax.scatter(row["nodes"] * (1 + shift), duration,
                           marker="^" if timed_out else "o", color=color,
                           facecolors="none" if timed_out else color)
        ax.set_title(f"Layer width {width}")
        ax.set_xlabel("Original vertices")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([100, 500, 1000], labels=["100", "500", "1000"])
        ax.set_yticks([2, 4, 6, 10], labels=["2", "4", "6", "10"])
        ax.minorticks_off()
        ax.grid(axis="y", color="#dedede", linewidth=.7)
    axes[0].set_ylabel("Global sifting time (s)")
    handles = [Line2D([], [], marker="o", linestyle="none", color=color, label=name)
               for _, name, color, _ in variants]
    fig.legend(handles=handles, loc="outside upper center", ncols=2, frameon=False)
    fig.text(.5, .012, "Open triangles indicate the 10-second cutoff.", ha="center", fontsize=8)
    fig.get_layout_engine().set(rect=(0, .055, 1, .945))
    fig.savefig(args.output)
    fig.savefig(args.output.with_suffix(".png"), dpi=160)


if __name__ == "__main__":
    main()
