"""段階別実行時間を中央値・四分位範囲つきの対数折れ線図にする。"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator


INPUT = Path("experiments/results/pipeline_runtime/summary_by_nodes.csv")
OUTPUT_DIR = Path("experiments/results/pipeline_runtime")
OUTPUT_PNG = OUTPUT_DIR / "pipeline_runtime_log_iqr_white.png"
OUTPUT_SVG = OUTPUT_DIR / "pipeline_runtime_log_iqr_white.svg"

PHASES = (
    ("step1", "階層割当1", "#268BEF", "o"),
    ("step2", "階層割当2", "#F28E2B", "s"),
    ("crossing", "交差削減", "#36B96B", "^"),
    ("coordinate", "座標割当", "#D94F91", "D"),
)


def load_rows():
    with INPUT.open(encoding="utf-8") as source:
        return [row for row in csv.DictReader(source) if row["scope"].startswith("n=")]


def seconds_label(value, _position):
    if value >= 1:
        return f"{value:g}秒"
    if value >= 0.01:
        return f"{value:g}秒"
    return f"{value * 1000:g}ms"


def main():
    rows = load_rows()
    nodes = [int(row["scope"].removeprefix("n=")) for row in rows]

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Hiragino Sans",
                "Yu Gothic",
                "Noto Sans CJK JP",
                "DejaVu Sans",
            ],
            "font.size": 15,
            "axes.edgecolor": "#777777",
            "axes.labelcolor": "#222222",
            "xtick.color": "#555555",
            "ytick.color": "#555555",
        }
    )

    figure, axis = plt.subplots(figsize=(16, 9), dpi=180, facecolor="white")
    axis.set_facecolor("white")

    for stem, label, color, marker in PHASES:
        median = [float(row[f"{stem}_median_seconds"]) for row in rows]
        q1 = [float(row[f"{stem}_q1_seconds"]) for row in rows]
        q3 = [float(row[f"{stem}_q3_seconds"]) for row in rows]
        axis.fill_between(nodes, q1, q3, color=color, alpha=0.13, linewidth=0)
        axis.plot(
            nodes,
            median,
            color=color,
            marker=marker,
            markersize=7,
            markeredgecolor="white",
            markeredgewidth=1.2,
            linewidth=2.8,
            label=label,
        )

    axis.set_yscale("log")
    axis.set_xlim(8, 102)
    axis.set_ylim(1e-4, 20)
    axis.set_xticks(nodes)
    axis.set_xlabel("頂点数", labelpad=12)
    axis.set_ylabel("実行時間（対数目盛）", labelpad=14)
    axis.yaxis.set_major_locator(LogLocator(base=10))
    axis.yaxis.set_major_formatter(FuncFormatter(seconds_label))
    axis.grid(axis="y", which="major", color="#D9D9D9", linewidth=1)
    axis.grid(axis="x", which="major", color="#EEEEEE", linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)

    axis.legend(
        loc="upper left",
        ncol=4,
        frameon=False,
        handlelength=2.4,
        columnspacing=1.5,
    )
    axis.text(
        0,
        1.055,
        "各処理の実行時間（中央値・四分位範囲）",
        transform=axis.transAxes,
        fontsize=21,
        fontweight="bold",
        color="#111111",
    )
    axis.text(
        0,
        1.015,
        "各頂点数20件　実線・点：中央値　帯：第1～第3四分位",
        transform=axis.transAxes,
        fontsize=13,
        color="#666666",
    )

    crossing_100 = float(rows[-1]["crossing_median_seconds"])
    axis.annotate(
        f"100頂点：{crossing_100:.2f}秒",
        xy=(100, crossing_100),
        xytext=(78, crossing_100 * 2.2),
        arrowprops={"arrowstyle": "->", "color": "#555555", "lw": 1.2},
        color="#222222",
        fontsize=14,
    )

    figure.subplots_adjust(left=0.10, right=0.97, bottom=0.12, top=0.83)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PNG, facecolor="white", bbox_inches="tight")
    figure.savefig(OUTPUT_SVG, facecolor="white", bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
