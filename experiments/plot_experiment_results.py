"""実験CSVから発表用のグラフ（PNG/SVG）を生成する。"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


ROOT = Path("experiments/results")
LAYER_DIR = ROOT / "layer_count_search"
CROSSING_DIR = ROOT / "crossing_reduction"
FRAMEWORK_DIR = ROOT / "torus_framework_ablation"

COLORS = {
    "initial": "#6B7280",
    "sifting": "#E69F00",
    "guard": "#0072B2",
    "proposed": "#0072B2",
    "exhaustive": "#6B7280",
    "optimal": "#009E73",
    "suboptimal": "#E69F00",
    "infeasible": "#CC79A7",
}


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def style_axis(axis):
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.65)
    axis.set_axisbelow(True)


def save_figure(figure, directory: Path, stem: str):
    figure.savefig(directory / f"{stem}.png", dpi=220, bbox_inches="tight")
    figure.savefig(directory / f"{stem}.svg", bbox_inches="tight")
    plt.close(figure)


def plot_layer_count_search():
    rows = read_csv(LAYER_DIR / "raw_results.csv")
    curves = read_csv(LAYER_DIR / "torus_count_curves.csv")
    nodes = sorted({int(row["nodes"]) for row in rows})

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.5))
    figure.suptitle("Automatic layer-count selection", fontsize=16, fontweight="medium")

    # (a) 全探索との一致
    exact = [int(row["exact_layer_count"]) for row in rows]
    proposed = [int(row["proposed_layer_count"]) for row in rows]
    max_layer = max(exact + proposed)
    axes[0].plot(
        [0, max_layer + 1],
        [0, max_layer + 1],
        color=COLORS["exhaustive"],
        linewidth=1.2,
        linestyle="--",
        label="exact match line",
    )
    axes[0].scatter(
        exact,
        proposed,
        s=38,
        color=COLORS["proposed"],
        edgecolor="white",
        linewidth=0.6,
        alpha=0.82,
    )
    axes[0].set_xlabel("Exhaustive-search layer count")
    axes[0].set_ylabel("Proposed layer count")
    axes[0].set_title("(a) Correctness: 48 / 48 match")
    axes[0].set_xlim(0, max_layer + 1)
    axes[0].set_ylim(0, max_layer + 1)
    axes[0].set_aspect("equal", adjustable="box")
    style_axis(axes[0])

    # (b) 頂点数ごとの実行時間中央値
    proposed_times = []
    exhaustive_times = []
    for node_count in nodes:
        group = [row for row in rows if int(row["nodes"]) == node_count]
        proposed_times.append(
            statistics.median(float(row["proposed_seconds"]) for row in group)
        )
        exhaustive_times.append(
            statistics.median(float(row["exhaustive_seconds"]) for row in group)
        )
    axes[1].plot(
        nodes,
        exhaustive_times,
        marker="s",
        linewidth=2,
        color=COLORS["exhaustive"],
        label="Exhaustive search",
    )
    axes[1].plot(
        nodes,
        proposed_times,
        marker="o",
        linewidth=2,
        color=COLORS["proposed"],
        label="Proposed",
    )
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Number of vertices")
    axes[1].set_ylabel("Median runtime (seconds, log scale)")
    axes[1].set_title("(b) Runtime by graph size")
    axes[1].legend(frameon=False)
    axes[1].set_xticks(nodes)
    style_axis(axes[1])

    # (c) 固定kの成否
    baselines = [
        ("k = 3", "fixed_3_torus_count"),
        ("k = 5", "fixed_5_torus_count"),
        ("k = ceil(sqrt(n))", "sqrt_torus_count"),
    ]
    optimal_counts = []
    suboptimal_counts = []
    infeasible_counts = []
    for _label, key in baselines:
        valid = [row for row in rows if row[key] != ""]
        optimal_count = sum(
            int(row[key]) == int(row["exact_torus_count"]) for row in valid
        )
        optimal_counts.append(optimal_count)
        suboptimal_counts.append(len(valid) - optimal_count)
        infeasible_counts.append(len(rows) - len(valid))
    x_values = range(len(baselines))
    axes[2].bar(
        x_values,
        optimal_counts,
        color=COLORS["optimal"],
        label="Optimal",
    )
    axes[2].bar(
        x_values,
        suboptimal_counts,
        bottom=optimal_counts,
        color=COLORS["suboptimal"],
        label="Suboptimal",
    )
    stacked_bottom = [a + b for a, b in zip(optimal_counts, suboptimal_counts)]
    axes[2].bar(
        x_values,
        infeasible_counts,
        bottom=stacked_bottom,
        color=COLORS["infeasible"],
        label="Infeasible",
    )
    for index, parts in enumerate(
        zip(optimal_counts, suboptimal_counts, infeasible_counts)
    ):
        bottom = 0
        for value in parts:
            if value:
                axes[2].text(index, bottom + value / 2, str(value), ha="center", va="center")
            bottom += value
    axes[2].set_xticks(list(x_values), [label for label, _ in baselines])
    axes[2].set_ylabel("Graphs (out of 48)")
    axes[2].set_title("(c) Fixed layer-count baselines")
    axes[2].legend(frameon=False, ncol=3, loc="upper center")
    style_axis(axes[2])

    figure.tight_layout()
    save_figure(figure, LAYER_DIR, "layer-count-search-charts")

    # 発表でT(k)の定義を説明するための代表例。
    selected = [
        row
        for row in curves
        if int(row["nodes"]) == 20 and int(row["seed"]) == 0
    ]
    figure, axis = plt.subplots(figsize=(8, 4.7))
    for family in ("dag", "mixed", "cyclic", "random"):
        family_rows = sorted(
            (row for row in selected if row["family"] == family),
            key=lambda row: int(row["layer_count"]),
        )
        valid_rows = [row for row in family_rows if row["torus_count"] != ""]
        axis.plot(
            [int(row["layer_count"]) for row in valid_rows],
            [int(row["torus_count"]) for row in valid_rows],
            marker="o",
            markersize=3.5,
            linewidth=1.8,
            label=family.capitalize(),
        )
    axis.set_xlabel("Layer count k")
    axis.set_ylabel("Minimum number of torus edges T(k)")
    axis.set_title("Representative T(k) curves (n=20, seed=0)")
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.legend(frameon=False, ncol=2)
    style_axis(axis)
    figure.tight_layout()
    save_figure(figure, LAYER_DIR, "torus-count-curves")


def plot_crossing_reduction():
    rows = read_csv(CROSSING_DIR / "raw_results.csv")
    cases = defaultdict(dict)
    for row in rows:
        key = (int(row["nodes"]), row["family"], int(row["seed"]))
        cases[key][row["method"]] = row

    method_order = (
        "barycenter_initial",
        "radial_sifting",
        "radial_sifting_guard",
    )
    labels = ("Initial\nbarycenter", "Radial\nsifting", "Sifting +\nglobal guard")
    colors = (COLORS["initial"], COLORS["sifting"], COLORS["guard"])

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.5))
    figure.suptitle("Crossing reduction on the flat torus", fontsize=16, fontweight="medium")

    # (a) 初期配置に対する交差数比。初期交差0のケースは除外。
    ratios = []
    for method in method_order:
        values = []
        for case in cases.values():
            initial = int(case["barycenter_initial"]["crossings"])
            if initial:
                values.append(int(case[method]["crossings"]) / initial)
        ratios.append(values)
    box = axes[0].boxplot(
        ratios,
        tick_labels=labels,
        patch_artist=True,
        showfliers=True,
        medianprops={"color": "#111827", "linewidth": 1.6},
    )
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.78)
    axes[0].axhline(1.0, color="#111827", linewidth=1, linestyle="--")
    axes[0].set_ylabel("Crossings / initial crossings")
    axes[0].set_title("(a) Per-graph crossing ratio")
    style_axis(axes[0])

    # (b) 改善・同率・悪化件数
    outcomes = []
    for method in method_order[1:]:
        comparison = []
        for case in cases.values():
            initial = int(case["barycenter_initial"]["crossings"])
            result = int(case[method]["crossings"])
            comparison.append((result > initial) - (result < initial))
        outcomes.append(
            (
                sum(value < 0 for value in comparison),
                sum(value == 0 for value in comparison),
                sum(value > 0 for value in comparison),
            )
        )
    x_values = range(2)
    improved = [value[0] for value in outcomes]
    equal = [value[1] for value in outcomes]
    worsened = [value[2] for value in outcomes]
    axes[1].bar(x_values, improved, color=COLORS["optimal"], label="Improved")
    axes[1].bar(x_values, equal, bottom=improved, color=COLORS["initial"], label="Equal")
    bottoms = [a + b for a, b in zip(improved, equal)]
    axes[1].bar(
        x_values,
        worsened,
        bottom=bottoms,
        color=COLORS["infeasible"],
        label="Worsened",
    )
    for index, parts in enumerate(outcomes):
        bottom = 0
        for value in parts:
            if value:
                axes[1].text(index, bottom + value / 2, str(value), ha="center", va="center")
            bottom += value
    axes[1].set_xticks(list(x_values), labels[1:])
    axes[1].set_ylabel("Graphs (out of 48)")
    axes[1].set_title("(b) Outcome against initial layout")
    axes[1].legend(frameon=False, ncol=3, loc="upper center")
    style_axis(axes[1])

    # (c) 頂点数別の交差数中央値
    node_counts = sorted({key[0] for key in cases})
    for method, label, color, marker in zip(
        method_order, labels, colors, ("s", "^", "o")
    ):
        medians = []
        for node_count in node_counts:
            values = [
                int(case[method]["crossings"])
                for key, case in cases.items()
                if key[0] == node_count
            ]
            medians.append(statistics.median(values))
        axes[2].plot(
            node_counts,
            medians,
            color=color,
            marker=marker,
            linewidth=2,
            label=label.replace("\n", " "),
        )
    axes[2].set_yscale("symlog", linthresh=10)
    axes[2].set_xlabel("Number of vertices")
    axes[2].set_ylabel("Median crossings (symlog scale)")
    axes[2].set_title("(c) Crossings by graph size")
    axes[2].set_xticks(node_counts)
    axes[2].legend(frameon=False)
    style_axis(axes[2])

    figure.tight_layout()
    save_figure(figure, CROSSING_DIR, "crossing-reduction-charts")


def plot_framework_ablation():
    rows = read_csv(FRAMEWORK_DIR / "crossing_ablation_raw.csv")
    cases = defaultdict(dict)
    for row in rows:
        key = (int(row["nodes"]), row["family"], int(row["seed"]))
        cases[key][row["variant"]] = row
    variants = (
        "order_only",
        "joint_psi",
        "joint_psi_rotation",
        "full_guard_rotation",
    )
    labels = ("Order only\n(fixed psi)", "Order +\npsi", "+ rotation", "+ global\nguard")
    colors = (COLORS["initial"], COLORS["sifting"], "#56B4E9", COLORS["guard"])

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.5))
    figure.suptitle("Ablation of torus crossing-reduction integration", fontsize=16)

    medians = [
        statistics.median(int(case[variant]["crossings"]) for case in cases.values())
        for variant in variants
    ]
    axes[0].bar(range(4), medians, color=colors)
    for index, value in enumerate(medians):
        axes[0].text(index, value, f"{value:.1f}", ha="center", va="bottom")
    axes[0].set_xticks(range(4), labels)
    axes[0].set_ylabel("Median crossings")
    axes[0].set_title("(a) Final crossing count")
    style_axis(axes[0])

    outcomes = []
    for variant in variants[1:]:
        differences = [
            int(case[variant]["crossings"])
            - int(case["order_only"]["crossings"])
            for case in cases.values()
        ]
        outcomes.append(
            (
                sum(value < 0 for value in differences),
                sum(value == 0 for value in differences),
                sum(value > 0 for value in differences),
            )
        )
    x_values = range(3)
    improved = [value[0] for value in outcomes]
    equal = [value[1] for value in outcomes]
    worsened = [value[2] for value in outcomes]
    axes[1].bar(x_values, improved, color=COLORS["optimal"], label="Improved")
    axes[1].bar(x_values, equal, bottom=improved, color=COLORS["initial"], label="Equal")
    bottoms = [a + b for a, b in zip(improved, equal)]
    axes[1].bar(
        x_values,
        worsened,
        bottom=bottoms,
        color=COLORS["infeasible"],
        label="Worsened",
    )
    for index, parts in enumerate(outcomes):
        bottom = 0
        for value in parts:
            if value:
                axes[1].text(index, bottom + value / 2, str(value), ha="center", va="center")
            bottom += value
    axes[1].set_xticks(list(x_values), labels[1:])
    axes[1].set_ylabel("Graphs (out of 48)")
    axes[1].set_title("(b) Outcome against fixed-psi sifting")
    axes[1].legend(frameon=False, ncol=3, loc="upper center")
    style_axis(axes[1])

    runtimes = [
        1000
        * statistics.median(
            float(case[variant]["runtime_seconds"]) for case in cases.values()
        )
        for variant in variants
    ]
    axes[2].bar(range(4), runtimes, color=colors)
    for index, value in enumerate(runtimes):
        axes[2].text(index, value, f"{value:.0f}", ha="center", va="bottom")
    axes[2].set_xticks(range(4), labels)
    axes[2].set_ylabel("Median runtime (ms)")
    axes[2].set_title("(c) Runtime")
    style_axis(axes[2])

    figure.tight_layout()
    save_figure(figure, FRAMEWORK_DIR, "framework-ablation-charts")


def plot_coordinate_ablation():
    rows = read_csv(FRAMEWORK_DIR / "coordinate_ablation_raw.csv")
    variants = ("uniform", "bk_no_smoothing", "bk_torus_smoothing")
    labels = ("Uniform", "BK", "BK + torus\nsmoothing")
    colors = (COLORS["initial"], COLORS["sifting"], COLORS["guard"])
    grouped = {
        variant: [row for row in rows if row["variant"] == variant]
        for variant in variants
    }

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.5))
    figure.suptitle("Ablation of torus coordinate assignment", fontsize=16)

    lengths = [
        statistics.median(float(row["mean_edge_length"]) for row in grouped[variant])
        for variant in variants
    ]
    axes[0].bar(range(3), lengths, color=colors)
    for index, value in enumerate(lengths):
        axes[0].text(index, value, f"{value:.3f}", ha="center", va="bottom")
    axes[0].set_xticks(range(3), labels)
    axes[0].set_ylabel("Median of mean periodic edge length")
    axes[0].set_title("(a) Edge length (lower is better)")
    style_axis(axes[0])

    mean_angles = [
        statistics.median(
            float(row["mean_abs_angle_degrees"]) for row in grouped[variant]
        )
        for variant in variants
    ]
    p95_angles = [
        statistics.median(
            float(row["p95_abs_angle_degrees"]) for row in grouped[variant]
        )
        for variant in variants
    ]
    width = 0.36
    x_values = list(range(3))
    axes[1].bar(
        [value - width / 2 for value in x_values],
        mean_angles,
        width,
        color="#56B4E9",
        label="Mean angle",
    )
    axes[1].bar(
        [value + width / 2 for value in x_values],
        p95_angles,
        width,
        color=COLORS["guard"],
        label="95th-percentile angle",
    )
    axes[1].set_xticks(x_values, labels)
    axes[1].set_ylabel("Absolute angle from flow direction (degrees)")
    axes[1].set_title("(b) Edge slope (lower is better)")
    axes[1].legend(frameon=False)
    style_axis(axes[1])

    runtimes = [
        1000
        * statistics.median(float(row["runtime_seconds"]) for row in grouped[variant])
        for variant in variants
    ]
    axes[2].bar(range(3), runtimes, color=colors)
    for index, value in enumerate(runtimes):
        axes[2].text(index, value, f"{value:.2f}", ha="center", va="bottom")
    axes[2].set_xticks(range(3), labels)
    axes[2].set_ylabel("Median runtime (ms)")
    axes[2].set_title("(c) Coordinate-assignment runtime")
    style_axis(axes[2])

    figure.tight_layout()
    save_figure(figure, FRAMEWORK_DIR, "coordinate-ablation-charts")


def main():
    if (LAYER_DIR / "raw_results.csv").exists():
        plot_layer_count_search()
    if (CROSSING_DIR / "raw_results.csv").exists():
        plot_crossing_reduction()
    if (FRAMEWORK_DIR / "crossing_ablation_raw.csv").exists():
        plot_framework_ablation()
    if (FRAMEWORK_DIR / "coordinate_ablation_raw.csv").exists():
        plot_coordinate_ablation()


if __name__ == "__main__":
    main()
