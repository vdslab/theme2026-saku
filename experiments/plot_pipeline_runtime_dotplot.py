"""頂点数・辺数ごとの全段階実行時間を1枚のドットプロットにする。"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator


INPUT = Path("experiments/results/pipeline_runtime/raw_results.csv")
OUTPUT_DIR = Path("experiments/results/pipeline_runtime")
OUTPUT_PNG = OUTPUT_DIR / "pipeline_runtime_dotplot_representative_white.png"
OUTPUT_SVG = OUTPUT_DIR / "pipeline_runtime_dotplot_representative_white.svg"
REPRESENTATIVE_NODES = {10, 40, 70, 100}

PHASES = (
    ("step1_seconds", "階層割当1", "#268BEF", "o", 54),
    ("step2_seconds", "階層割当2", "#F28E2B", "s", 50),
    ("crossing_seconds", "交差削減", "#36B96B", "^", 58),
    ("coordinate_seconds", "座標割当", "#D94F91", "D", 46),
    ("total_seconds", "総時間", "#333333", "X", 60),
)


def load_means():
    groups = defaultdict(list)
    with INPUT.open(encoding="utf-8") as source:
        for row in csv.DictReader(source):
            groups[(int(row["nodes"]), int(row["edges"]))].append(row)

    return {
        key: {
            metric: statistics.mean(float(row[metric]) for row in rows)
            for metric, _label, _color, _marker, _size in PHASES
        }
        for key, rows in groups.items()
    }


def time_label(value, _position=None):
    if value >= 1:
        return f"{value:g}秒"
    if value >= 0.1:
        return f"{value:g}秒"
    if value >= 0.01:
        return f"{value * 1000:g}ms"
    return f"{value * 1000:g}ms"


def main():
    means = load_means()
    conditions = sorted(
        condition for condition in means if condition[0] in REPRESENTATIVE_NODES
    )
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
            "font.size": 13,
            "axes.edgecolor": "#888888",
            "axes.labelcolor": "#333333",
            "xtick.color": "#555555",
            "ytick.color": "#333333",
        }
    )

    figure, axis = plt.subplots(figsize=(16, 8), dpi=180, facecolor="white")
    axis.set_facecolor("white")

    for pair_index in range(0, len(conditions), 2):
        top = y_positions[pair_index] + 0.48
        bottom = y_positions[pair_index + 1] - 0.48
        if (pair_index // 2) % 2 == 0:
            axis.axhspan(bottom, top, color="#F5F8FC", zorder=0)

    for metric, label, color, marker, size in PHASES:
        values = [means[condition][metric] for condition in conditions]
        axis.scatter(
            values,
            y_positions,
            color=color,
            marker=marker,
            s=size,
            edgecolor="white",
            linewidth=0.8,
            label=label,
            zorder=3,
        )

    axis.set_xscale("log")
    axis.set_xlim(2e-4, 20)
    axis.set_ylim(-0.7, len(conditions) - 0.3)
    axis.set_yticks(y_positions, labels)
    axis.xaxis.set_major_locator(LogLocator(base=10))
    axis.xaxis.set_major_formatter(FuncFormatter(time_label))
    axis.set_xlabel("平均実行時間（対数目盛）", labelpad=12)
    axis.grid(axis="x", which="major", color="#D5D5D5", linewidth=1)
    axis.grid(axis="x", which="minor", color="#EEEEEE", linewidth=0.6)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0, pad=10)

    for index in range(1, len(conditions), 2):
        boundary = y_positions[index] - 0.5
        axis.axhline(boundary, color="#D8D8D8", linewidth=0.8, zorder=1)

    axis.legend(
        loc="lower center",
        bbox_to_anchor=(0.58, 1.015),
        ncol=5,
        frameon=False,
        columnspacing=1.6,
        handletextpad=0.5,
    )
    axis.set_title(
        "代表的な頂点数・辺数における段階別実行時間",
        loc="left",
        fontsize=23,
        fontweight="bold",
        pad=88,
    )
    axis.text(
        0,
        1.085,
        "各条件10件の平均（再配線確率2水準 × seed 5）",
        transform=axis.transAxes,
        color="#666666",
        fontsize=13,
    )

    figure.subplots_adjust(left=0.16, right=0.97, bottom=0.09, top=0.78)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PNG, facecolor="white", bbox_inches="tight")
    figure.savefig(OUTPUT_SVG, facecolor="white", bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
