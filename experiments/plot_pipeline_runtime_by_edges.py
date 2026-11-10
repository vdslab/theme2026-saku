"""頂点数と辺数の組合せごとに段階別平均実行時間を比較する。"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


INPUT = Path("experiments/results/pipeline_runtime/raw_results.csv")
OUTPUT_DIR = Path("experiments/results/pipeline_runtime")
OUTPUT_PNG = OUTPUT_DIR / "pipeline_runtime_by_nodes_edges_white.png"
OUTPUT_SVG = OUTPUT_DIR / "pipeline_runtime_by_nodes_edges_white.svg"

PANELS = (
    ("step1_seconds", "階層割当1"),
    ("step2_seconds", "階層割当2"),
    ("crossing_seconds", "交差削減"),
    ("coordinate_seconds", "座標割当"),
    ("total_seconds", "総時間"),
)

SERIES = (
    ("E=V", "#268BEF", "o"),
    ("E=2V", "#F28E2B", "s"),
)


def load_means():
    groups = defaultdict(list)
    with INPUT.open(encoding="utf-8") as source:
        for row in csv.DictReader(source):
            nodes = int(row["nodes"])
            edges = int(row["edges"])
            density = "E=V" if edges == nodes else "E=2V"
            groups[(nodes, density)].append(row)

    result = {}
    for key, rows in groups.items():
        result[key] = {
            metric: statistics.mean(float(row[metric]) for row in rows)
            for metric, _label in PANELS
        }
    return result


def time_label(value, _position=None):
    if value >= 1:
        return f"{value:g}秒"
    if value >= 0.1:
        return f"{value:.1f}秒"
    if value >= 0.01:
        return f"{value:.2f}秒"
    return f"{value * 1000:g}ms"


def main():
    means = load_means()
    nodes = list(range(10, 101, 10))

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Hiragino Sans",
                "Yu Gothic",
                "Noto Sans CJK JP",
                "DejaVu Sans",
            ],
            "font.size": 12,
            "axes.edgecolor": "#888888",
            "axes.labelcolor": "#333333",
            "xtick.color": "#555555",
            "ytick.color": "#555555",
        }
    )

    figure, axes = plt.subplots(2, 3, figsize=(16, 9), dpi=180, facecolor="white")
    axes = axes.flatten()

    for axis, (metric, title) in zip(axes, PANELS):
        axis.set_facecolor("white")
        for density, color, marker in SERIES:
            values = [means[(node, density)][metric] for node in nodes]
            axis.plot(
                nodes,
                values,
                color=color,
                marker=marker,
                markersize=5.5,
                markeredgecolor="white",
                markeredgewidth=0.9,
                linewidth=2.4,
                label=density,
            )
            axis.annotate(
                time_label(values[-1]),
                xy=(nodes[-1], values[-1]),
                xytext=(-5, 8 if density == "E=2V" else -16),
                textcoords="offset points",
                ha="right",
                color=color,
                fontsize=11,
            )

        axis.set_title(title, loc="left", fontsize=16, fontweight="bold", pad=8)
        axis.set_xlim(8, 102)
        axis.set_ylim(bottom=0)
        axis.set_xticks([20, 40, 60, 80, 100])
        axis.yaxis.set_major_formatter(FuncFormatter(time_label))
        axis.grid(axis="y", color="#DDDDDD", linewidth=0.9)
        axis.grid(axis="x", color="#F0F0F0", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_xlabel("頂点数 V")
        axis.set_ylabel("平均実行時間")

    legend_axis = axes[-1]
    legend_axis.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    legend_axis.legend(
        handles,
        labels,
        loc="center",
        frameon=False,
        fontsize=17,
        handlelength=3,
        labelspacing=1.4,
    )
    legend_axis.text(
        0.5,
        0.25,
        "各点は10件の平均\n（再配線確率2水準 × seed 5）",
        ha="center",
        va="center",
        color="#555555",
        fontsize=13,
        linespacing=1.6,
        transform=legend_axis.transAxes,
    )

    figure.suptitle(
        "頂点数・辺数別の実行時間",
        x=0.07,
        y=0.98,
        ha="left",
        fontsize=23,
        fontweight="bold",
    )
    figure.subplots_adjust(left=0.07, right=0.97, bottom=0.08, top=0.90, wspace=0.30, hspace=0.42)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PNG, facecolor="white", bbox_inches="tight")
    figure.savefig(OUTPUT_SVG, facecolor="white", bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
