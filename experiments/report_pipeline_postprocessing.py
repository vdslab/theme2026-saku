"""Regenerate paired statistics and fixed-scale figures from saved outcomes."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
from statistics import median

from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle

from compare_pipeline_postprocessing import CONFIGS, PREVIOUS, write_csv

METHODS = tuple(CONFIGS)
TIME_METRICS = ("total_seconds", "sifting_seconds", "algo2_seconds",
                "boundary_seconds", "coordinate_seconds")
GROUPS = {"all": "全体", "ring": "円環沿い", "random": "ランダム方向",
          "dag": "有向閉路なし", "public": "公開ネットワーク"}
METRICS = {
    "geometric_crossings": "幾何交差", "bends": "折れ",
    "either_seam_edges": "境界を通る元辺", "total_edge_length": "中心線総延長",
    "dummy_inner_geometric_crossings": "ダミー間線分の幾何交差",
    "total_seconds": "後段全体（秒）", "sifting_seconds": "sifting（秒）",
    "algo2_seconds": "Algo2（秒）", "boundary_seconds": "境界処理（秒）",
    "coordinate_seconds": "座標割当（秒）", "pre": "初回sifting直後の埋め込み交差",
    "post": "最終境界処理後の埋め込み交差",
}


def paired_stats(values):
    return {"n": len(values), "median_delta": median(values) if values else None,
            "fewer": sum(x < 0 for x in values), "tied": sum(x == 0 for x in values),
            "more": sum(x > 0 for x in values)}


def data_row(case, method, result):
    attempts = result.get("attempts", [])
    final = next((a for a in reversed(attempts) if "post" in a), {})
    post = final.get("post", {})
    calls = {op["call"] for op in final.get("operations", [])}
    seam_used = ("joint" if "optimize_joint_seam" in calls
                 else "legacy" if "optimize_seam" in calls else None)
    return {"case": case["case"], "family": case["family"], "method": method,
            **{k: v for k, v in result.items()
               if k not in ("attempts", "drawing", "geometry", "coordinates_attempts")},
            **result.get("geometry", {}),
            "seam_used": seam_used,
            "pre": attempts[0].get("pre", {}).get("crossings") if attempts else None,
            "post": post.get("crossings"),
            "post_boundary_edges": post.get("either_seam_edges"),
            "global_rounds": sum(a["global_rounds"] for a in attempts),
            "radial_strip_passes": sum(a["radial_strip_passes"] for a in attempts),
            "fallback_timed_stages_seconds": (
                sum(sum(a["times"].values()) for a in attempts[1:])
                + sum(c["seconds"] for c in result.get("coordinates_attempts", []) if c["attempt"] > 1)
                if attempts else None
            ),
            "first": bool(case["execution_order"] and case["execution_order"][0] == method)}


def draw_pair(path, case):
    outcomes = case["outcomes"]
    dpi, scale, margin, gap, top = 120, 72, 22, 30, 78
    width = outcomes["radial"]["drawing"]["bounds"][2] * scale
    heights = {m: outcomes[m]["drawing"]["bounds"][3] * scale for m in METHODS}
    w = int(2 * width + 2 * margin + gap)
    h = math.ceil(max(heights.values()) + top + 2 * margin)
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi, facecolor="white")
    fig.text(margin / w, 1 - 10 / h, case["case"], fontsize=11, weight="bold", va="top")
    for i, (method, title) in enumerate(zip(METHODS, ("Radial + Algo2 + UNWIND", "Current global"))):
        result = outcomes[method]
        metrics = result["geometry"]
        xmin, ymin, extent, period = result["drawing"]["bounds"]
        x = margin + i * (width + gap)
        y = margin + (max(heights.values()) - heights[method]) / 2
        ax = fig.add_axes((x / w, y / h, width / w, heights[method] / h))
        ax.set(xlim=(xmin, xmin + extent), ylim=(ymin + period, ymin))
        ax.set_axis_off()
        ax.add_patch(Rectangle((xmin, ymin), extent, period, fill=False,
                               edgecolor="#82909a", linewidth=.7, clip_on=False))
        fig.text(x / w, 1 - 32 / h, title, fontsize=10, weight="bold", va="top")
        fig.text(x / w, 1 - 52 / h,
                 f"Crossings {metrics['geometric_crossings']}  |  Bends {metrics['bends']}"
                 f"  |  Boundary edges {metrics['either_seam_edges']}",
                 fontsize=8, va="top")
        routes = result["drawing"]["routes"]
        for route in routes:
            pieces = route["pieces"]
            color = "#526979"
            ax.add_collection(LineCollection(pieces, linewidths=.70, colors=color, alpha=.77))
            if pieces:
                start, end = pieces[-1]
                length = math.dist(start, end)
                if length > .16:
                    tip = [b + (a - b) * .11 / length for a, b in zip(start, end)]
                    tail = [b + (a - b) * .15 / length for a, b in zip(start, end)]
                    ax.annotate("", tip, tail, arrowprops={"arrowstyle": "-|>", "lw": .55,
                                "color": color, "mutation_scale": 7, "shrinkA": 0, "shrinkB": 0})
        for node, (xnode, ynode) in result["drawing"]["nodes"]:
            ax.scatter(xnode, ynode, s=77, color="white", edgecolor="#344753", linewidth=.65, zorder=3)
            ax.text(xnode, ynode, str(node), ha="center", va="center", fontsize=5.3, zorder=4)
        fig.canvas.draw()
        assert abs(ax.get_window_extent().width / extent - scale) < 1e-7
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def main(output):
    records = json.loads((output / "inputs.json").read_text())
    cases = [json.loads((output / f"{r['case']}.json").read_text()) for r in records]
    with PREVIOUS.open() as stream:
        previous = {(r["case"], r["method"]): r for r in csv.DictReader(stream)}
    rows, pairs, summary, completion, examples, trial_times = [], [], [], [], [], []
    for case in cases:
        name, family = case["case"], case["family"]
        radial, global_ = (data_row(case, method, case["outcomes"][method]) for method in METHODS)
        rows.extend((radial, global_))
        complete = radial["status"] == global_["status"] == "ok"
        pair = {"case": name, "family": family, "complete": complete,
                "radial_status": radial["status"], "global_status": global_["status"]}
        for metric in METRICS:
            if global_.get(metric) is None or radial.get(metric) is None:
                continue
            delta = global_[metric] - radial[metric]
            if metric in TIME_METRICS:
                pair[f"{metric}_all_trials"] = delta
            if complete or metric in ("pre", "post"):
                pair[metric] = delta
        for method_row in (radial, global_):
            method = method_row["method"]
            if method_row["pre"] is not None and method_row["post"] is not None:
                pair[f"{method}_post_change"] = method_row["post"] - method_row["pre"]
        if complete:
            before = [previous[name, m]["geometric_crossings"] for m in METHODS]
            if all(before):
                pair["previous_geometry"] = int(before[1]) - int(before[0])
                pair["geometry_change"] = pair["geometric_crossings"] - pair["previous_geometry"]
        pairs.append(pair)

    for group in GROUPS:
        subset = [p for p in pairs if group in ("all", p["family"])]
        for metric in (*METRICS, "previous_geometry", "geometry_change",
                       "radial_post_change", "global_post_change"):
            summary.append({"scope": group, "metric": metric,
                            **paired_stats([p[metric] for p in subset if metric in p])})
        for metric in TIME_METRICS:
            key = f"{metric}_all_trials"
            trial_times.append({"scope": group, "metric": metric,
                                **paired_stats([p[key] for p in subset if key in p])})
        complete = sum(p["complete"] for p in subset)
        completion.append({"scope": group, "inputs": len(subset), "trials": 2 * len(subset),
                           "radial_fail": sum(p["radial_status"] != "ok" for p in subset),
                           "global_fail": sum(p["global_status"] != "ok" for p in subset),
                           "paired_complete": complete})

    candidates = [p for p in pairs if p["complete"]]
    selected = []
    if candidates:
        for key in (min(candidates, key=lambda p: p["geometric_crossings"]),
                    max(candidates, key=lambda p: p["geometric_crossings"])):
            if key["case"] not in selected:
                selected.append(key["case"])
    if any(p["case"] == "ws-30-42-ring" for p in candidates) and "ws-30-42-ring" not in selected:
        selected.append("ws-30-42-ring")
    for name in selected:
        filename = f"figure_{name}.png"
        draw_pair(output / filename, next(c for c in cases if c["case"] == name))
        examples.append({"case": name, "filename": filename, "pixels_per_layer": 72})

    write_csv(output, "measurements.csv", rows)
    write_csv(output, "paired.csv", pairs)
    write_csv(output, "summary.csv", summary)
    write_csv(output, "completion.csv", completion)
    write_csv(output, "timing_all_trials.csv", trial_times)
    write_csv(output, "examples.csv", examples)
    print("Completion", completion)
    print("Seam", Counter((r["method"], r.get("seam_used"), r.get("fallback")) for r in rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    main(parser.parse_args().output)
