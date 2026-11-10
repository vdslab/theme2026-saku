"""代表8条件の段階別平均実行時間を横向き積み上げ棒で示す。"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


INPUT = Path("experiments/results/pipeline_runtime/raw_results.csv")
OUTPUT_DIR = Path("experiments/results/pipeline_runtime")
OUTPUT_PNG = OUTPUT_DIR / "pipeline_runtime_representative_stacked_white.png"
OUTPUT_SVG = OUTPUT_DIR / "pipeline_runtime_representative_stacked_white.svg"
REPRESENTATIVE_NODES = {10, 40, 70, 100}

PHASES = (
    ("step1_seconds", "階層数取得", "#268BEF"),
    ("step2_seconds", "階層割当", "#F28E2B"),
    ("crossing_seconds", "交差削減", "#36B96B"),
    ("coordinate_seconds", "座標割当", "#D94F91"),
)


def load_means():
    groups = defaultdict(list)
    with INPUT.open(encoding="utf-8") as source:
        for row in csv.DictReader(source):
            nodes = int(row["nodes"])
            if nodes in REPRESENTATIVE_NODES:
                groups[(nodes, int(row["edges"]))].append(row)

    return {
        condition: {
            metric: statistics.mean(float(row[metric]) for row in rows)
            for metric, _label, _color in PHASES
        }
        for condition, rows in groups.items()
    }


def seconds_label(value, _position=None):
    return f"{value:g}秒"


def main():
    means = load_means()
    conditions = sorted(means)
    labels = [f"V={nodes}, E={edges}" for nodes, edges in conditions]
    y_positions = list(range(len(conditions)))[::-1]

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Hiragino Sans",
                "Yu Gothic",
                "Noto Sans CJK JP",
                "DejaVu Sans",
            ],
            "font.size": 14,
            "axes.edgecolor": "#888888",
            "axes.labelcolor": "#333333",
            "xtick.color": "#555555",
            "ytick.color": "#333333",
        }
    )

    figure, axis = plt.subplots(figsize=(16, 8), dpi=180, facecolor="white")
    axis.set_facecolor("white")
    left = [0.0] * len(conditions)

    for metric, label, color in PHASES:
        values = [means[condition][metric] for condition in conditions]
        axis.barh(
            y_positions,
            values,
            left=left,
            height=0.58,
            color=color,
            edgecolor="white",
            linewidth=0.7,
            label=label,
        )
        left = [base + value for base, value in zip(left, values)]

    for y, total in zip(y_positions, left):
        label = f"{total:.3f}秒" if total < 1 else f"{total:.2f}秒"
        axis.text(
            total + 0.12,
            y,
            label,
            va="center",
            ha="left",
            color="#222222",
            fontsize=13,
            fontweight="bold",
        )

    for group_index in range(4):
        if group_index % 2 == 0:
            upper = y_positions[group_index * 2] + 0.48
            lower = y_positions[group_index * 2 + 1] - 0.48
            axis.axhspan(lower, upper, color="#F5F8FC", zorder=0)

    axis.set_yticks(y_positions, labels)
    axis.set_xlim(0, max(left) * 1.13)
    axis.xaxis.set_major_formatter(FuncFormatter(seconds_label))
    axis.set_xlabel("平均実行時間", labelpad=12)
    axis.grid(axis="x", color="#DDDDDD", linewidth=0.9)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0, pad=10)

    for index in range(1, len(conditions), 2):
        axis.axhline(y_positions[index] - 0.5, color="#D8D8D8", linewidth=0.8)

    axis.legend(
        loc="lower center",
        bbox_to_anchor=(0.54, 1.015),
        ncol=4,
        frameon=False,
        columnspacing=1.8,
    )
    figure.subplots_adjust(left=0.16, right=0.97, bottom=0.10, top=0.88)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PNG, facecolor="white", bbox_inches="tight")
    figure.savefig(OUTPUT_SVG, facecolor="white", bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
