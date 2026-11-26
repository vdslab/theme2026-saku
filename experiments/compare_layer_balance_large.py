"""Matched diff vs diff_square experiment on larger generated cyclic graphs."""

import argparse
import csv
from hashlib import sha256
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

import networkx as nx

from run_torus_study import ROOT
from torus_study.inputs import generate
from torus_study.stages import assignment_metrics, record_solver, subdivision_metrics
from torus_study.geometry import route_metrics, torus_routes

import sys
sys.path.insert(0, str(ROOT / "src"))

from torus_layout import pipeline
from torus_layout.crossing import count_crossings
from torus_layout.drawing.figure import create_figure
from torus_layout.drawing.models import DrawingOptions
from torus_layout.layering import balance_layers, find_minimum_configuration
from torus_layout.models import LayerSearchResult, PipelineConfig


FAMILIES = ("random", "scc_chain", "watts_strogatz")
METHODS = (("linear", "diff"), ("square", "diff_square"))


def manifest(family, n, index):
    seed = 926_000 + n * 100 + FAMILIES.index(family) * 10 + index
    case = generate(family, n, 2, seed)
    return {"case": case.id, "family": family, "nodes": len(case.graph.nodes),
            "edges": len(case.graph.edges), "seed": seed,
            "edge_list": [list(edge) for edge in case.graph.edges]}, case


def status_from_exception(exc, gp):
    if isinstance(exc, gp.GurobiError) and exc.errno == gp.GRB.Error.SIZE_LIMIT_EXCEEDED:
        return "license_size_limit"
    if isinstance(exc, TimeoutError):
        return "timeout"
    return "error"


def add_solver_gaps(trace):
    for record in trace:
        if "objective" in record and "bound" in record:
            record["relative_gap"] = abs(record["objective"] - record["bound"]) / max(abs(record["objective"]), 1e-12)


def save_pair(case_id, family, results, directory):
    """Render equal-width panels; a layer occupies the same pixel width in both."""
    import matplotlib.pyplot as plt
    from torus_layout.drawing.preparation import prepare_drawing
    from torus_layout.drawing.artists import draw_edges, draw_nodes

    valid = [results.get(name) for name, _ in METHODS]
    if not all(valid):
        return
    layers = valid[0]["search"].layer_count
    if any(x["search"].layer_count != layers for x in valid):
        return
    options = DrawingOptions(figsize=(max(7.0, layers * 1.0), 5.0),
                             show_legend=False, show_layer_labels=False,
                             draw_dummy_nodes=True, tile_surroundings=False)
    prepared_items = []
    for name, _ in METHODS:
        result = results[name]["pipeline"]
        data = prepare_drawing(
            list(result.subdivided.original_nodes), list(result.subdivided.graph.edges),
            result.subdivided.layers, order=result.crossing.order,
            psi=result.crossing.winding_numbers, t_val=result.subdivided.torus_flags,
            pos=result.coordinates.positions, draw_dummy_nodes=True,
            figsize=options.figsize, dpi=options.dpi, show_legend=False,
            show_layer_labels=False, node_size=options.node_size,
            dummy_node_size=options.dummy_node_size, font_size=options.font_size,
            edge_width=options.edge_width, vertical_period=result.coordinates.period,
            tile_surroundings=False)
        prepared_items.append((data, result, results[name], name))
    y_low = min(item[0].y_min for item in prepared_items)
    y_high = max(item[0].y_max for item in prepared_items)
    vertical_span = y_high - y_low + 1.0
    unit_inches = 0.28
    panel_width = layers * unit_inches
    panel_height = vertical_span * unit_inches
    fig, axes = plt.subplots(1, 2, figsize=(2 * panel_width + 1.4, panel_height + 1.4),
                             constrained_layout=True)
    for ax, (data, result, stats, name) in zip(axes, prepared_items):
        ax.set_xlim(-0.5, layers - 0.5)
        ax.set_ylim(y_low - 0.5, y_high + 0.5)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{name} · L={layers}, T={stats['search'].torus_count}\n"
                     f"dummy={stats['dummy_nodes']} · max span={stats['max_span']}\n"
                     f"geometric crossings={stats['geometric_crossings']} · bends={stats['bends']}",
                     fontsize=7)
        draw_edges(ax, data, options)
        draw_nodes(ax, data, options)
    fig.suptitle(f"{case_id} · {family} (equal layer width)")
    fig.savefig(directory / f"{case_id}.png", dpi=160)
    fig.savefig(directory / f"{case_id}.svg")
    plt.close(fig)


def run_one(case, args, order):
    import gurobipy as gp
    from torus_layout.layering.lib.solver import create_gurobi_env

    graph = case.graph
    rows, retained = [], {}
    trace = []
    start = perf_counter()
    search = None
    try:
        with record_solver(argparse.Namespace(local_license=True, solver_seconds=args.solver_seconds), trace):
            search = find_minimum_configuration(graph)
        add_solver_gaps(trace)
        search_seconds = perf_counter() - start
        if search.layer_count is None or search.torus_count is None:
            return [{"case": case.id, "stage": "search", "status": "no_solution",
                     "search_seconds": search_seconds, "solver": trace}]
    except (gp.GurobiError, TimeoutError, RuntimeError, ValueError) as exc:
        return [{"case": case.id, "stage": "search", "status": status_from_exception(exc, gp),
                 "error": str(exc), "search_seconds": perf_counter()-start, "solver": trace}]

    rows = [{"case": case.id, "stage": "search", "status": "ok",
             "seconds": search_seconds, "layers": search.layer_count,
             "wraps": search.torus_count, "solver": trace}]
    for method_name, balance_method in order:
        solver_trace = []
        t0 = perf_counter()
        try:
            with record_solver(argparse.Namespace(local_license=True, solver_seconds=args.solver_seconds), solver_trace):
                assignment = balance_layers(graph, search.torus_count, search.layer_count, balance_method)
            add_solver_gaps(solver_trace)
            elapsed = perf_counter() - t0
            if not assignment.node_to_layer:
                solver_status = solver_trace[-1]["status"] if solver_trace else None
                no_solution_status = "timeout_no_solution" if solver_status == gp.GRB.TIME_LIMIT else "no_incumbent"
                rows.append({"case": case.id, "stage": "assignment", "method": method_name,
                             "status": no_solution_status, "seconds": elapsed, "solver": solver_trace})
                continue
            metrics = assignment_metrics(graph, assignment, search.layer_count, search.torus_count)
            theoretical = metrics["predicted_dummies"]
            if metrics["assignment_violations"]:
                rows.append({"case": case.id, "stage": "assignment", "method": method_name,
                             "status": "invalid_assignment", "seconds": elapsed, **metrics,
                             "solver": solver_trace})
                continue
            retained[method_name] = {"assignment": assignment, "search": search, **metrics,
                                     "assignment_seconds": elapsed, "solver": solver_trace,
                                     "optimality_status": ("optimal" if solver_trace and solver_trace[-1]["status"] == gp.GRB.OPTIMAL else "feasible_not_proven_optimal"),
                                     "theoretical_dummies": theoretical}
            rows.append({"case": case.id, "stage": "assignment", "method": method_name,
                         "status": "ok", "optimality_status": retained[method_name]["optimality_status"], "seconds": elapsed, **metrics,
                         "solver": solver_trace})
        except (gp.GurobiError, TimeoutError, RuntimeError, ValueError, ArithmeticError) as exc:
            rows.append({"case": case.id, "stage": "assignment", "method": method_name,
                         "status": status_from_exception(exc, gp), "error": str(exc),
                         "seconds": perf_counter()-t0, "solver": solver_trace})

    for method_name, data in list(retained.items()):
        try:
            config = PipelineConfig(balance_method="diff", rounds=PipelineConfig().rounds)
            with patch.object(pipeline, "assign_layers", return_value=(search, data["assignment"])):
                t0 = perf_counter()
                layout = pipeline.run_pipeline(graph, config)
                drawing_seconds = perf_counter() - t0
            if layout is None:
                raise RuntimeError("pipeline returned no layout")
            paths, submetrics = subdivision_metrics(graph, layout.subdivided)
            actual = submetrics["dummy_nodes"]
            if actual != data["theoretical_dummies"] or submetrics["unit_span_violations"]:
                raise ValueError("dummy count or unit-span validation failed")
            t0 = perf_counter()
            routes, bounds = torus_routes(paths, layout.subdivided, layout.crossing, layout.coordinates)
            geometry = route_metrics(routes, bounds)
            geometry_seconds = perf_counter() - t0
            data.update({"pipeline": layout, "dummy_nodes": actual, "drawing_seconds": drawing_seconds,
                         "geometry_seconds": geometry_seconds,
                         "geometric_crossings": geometry["geometric_crossings"],
                         "bends": geometry["bends"], "boundary_original_edges": geometry["either_seam_edges"],
                         "total_edge_length": geometry["total_edge_length"],
                         "max_edge_length": geometry["max_edge_length"],
                         "pipeline_crossing_seconds": layout.crossing_time,
                         "coordinate_seconds": layout.coordinate_time,
                         "coordinate_fallback": layout.seam_method_used == "legacy",
                         "status": "ok"})
            rows.append({"case": case.id, "stage": "drawing", "method": method_name,
                         "status": "ok", "drawing_seconds": drawing_seconds,
                         "crossing_seconds": layout.crossing_time,
                         "coordinate_seconds": layout.coordinate_time,
                         "geometry_seconds": geometry_seconds, **submetrics, **geometry,
                         "coordinate_fallback": layout.seam_method_used == "legacy"})
        except (gp.GurobiError, TimeoutError, RuntimeError, ValueError, ArithmeticError, OSError) as exc:
            data["status"] = status_from_exception(exc, gp)
            rows.append({"case": case.id, "stage": "drawing", "method": method_name,
                         "status": data["status"], "error": str(exc)})
    for row in rows:
        row.update({"family": case.family, "nodes": len(graph.nodes), "edges": len(graph.edges),
                    "layers": search.layer_count, "wraps": search.torus_count,
                    "search_seconds": search_seconds})
    return rows, retained


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--solver-seconds", type=float, default=4.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/layer-balance-mpl")
    cases = []
    sizes = (20, 40, 60, 80, 100)
    for n in sizes:
        for family in FAMILIES:
            count = 1 if args.smoke else (10 if family == "watts_strogatz" else 5)
            for index in range(count):
                rec, case = manifest(family, n, index)
                cases.append((rec, case))
    if args.limit:
        cases = cases[:args.limit]
    with (args.output / "inputs.jsonl").open("w", encoding="utf-8") as f:
        for rec, _ in cases:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    settings = {"solver_seconds": args.solver_seconds, "threads": 1, "solver_seed": 0,
                "jobs": 1, "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                "sizes": sizes,
                "per_size_counts": {family: sum(rec["family"] == family and rec["nodes"] == sizes[0]
                                                for rec, _ in cases) for family in FAMILIES},
                "families": FAMILIES, "edge_density": 2,
                "methods": dict(METHODS), "default_pipeline_config": str(PipelineConfig()),
                "order": "alternates per case; starts linear on even case index",
                "source_sha256": __import__("run_torus_study").source_fingerprint(),
                "experiment_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output / "settings.json").write_text(json.dumps(settings, indent=2)+"\n", encoding="utf-8")
    all_rows, retained_cases = [], {}
    for i, (rec, case) in enumerate(cases):
        order = METHODS if i % 2 == 0 else tuple(reversed(METHODS))
        outcome = run_one(case, args, order)
        if isinstance(outcome, tuple):
            rows, retained = outcome
        else:
            rows, retained = outcome, {}
        for row in rows:
            row.update({"family": rec["family"], "nodes": rec["nodes"], "edges": rec["edges"]})
            all_rows.append(row)
        retained_cases[case.id] = retained
        with (args.output / "rows.jsonl").open("a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str)+"\n")
        print(f"{i+1}/{len(cases)} {case.id}: " + ", ".join(f"{k}={v.get('status')}" for k,v in retained.items()), flush=True)
    write_outputs(args.output, all_rows, retained_cases)
    # Preserve representative complete paired drawings if there are completed pairs.
    drawing_dir = args.output / "drawings"
    drawing_dir.mkdir()
    candidates = []
    joint_improvements = []
    tradeoffs = []
    for case_id, result in retained_cases.items():
        if all(result.get(name, {}).get("status") == "ok" for name, _ in METHODS):
            linear, square = result["linear"], result["square"]
            candidates.append((case_id, result))
            if square["max_span"] < linear["max_span"] and square["geometric_crossings"] < linear["geometric_crossings"]:
                joint_improvements.append((case_id, result))
            if square["max_span"] < linear["max_span"] and (
                square["dummy_nodes"] > linear["dummy_nodes"] or
                square["geometric_crossings"] > linear["geometric_crossings"]
            ):
                tradeoffs.append((case_id, result))
    selected = []
    for pool in (joint_improvements, tradeoffs):
        if pool:
            selected.append(pool[0])
    if not selected and candidates:
        selected.append(candidates[0])
    for case_id, result in selected:
        family = next(rec["family"] for rec, c in cases if c.id == case_id)
        save_pair(case_id, family, result, drawing_dir)


def write_outputs(output, rows, retained):
    fields = sorted({key for row in rows for key in row if key != "solver"})
    with (output/"results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict,list)) else v
                          for k,v in row.items() if k != "solver"} for row in rows)
    with (output/"solver_traces.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            if row.get("solver"):
                f.write(json.dumps({"case": row["case"], "stage": row["stage"],
                                    "method": row.get("method"), "solver": row["solver"]})+"\n")
    summarize(output, rows)


def summarize(output, rows):
    by_case = defaultdict(dict)
    for row in rows:
        if row.get("stage") in ("assignment", "drawing"):
            by_case[row["case"]][(row["stage"], row.get("method"))] = row
    paired = []
    for case, methods in by_case.items():
        meta = next(r for r in rows if r["case"] == case)
        lin = methods.get(("assignment", "linear"), {})
        sq = methods.get(("assignment", "square"), {})
        ld = methods.get(("drawing", "linear"), {})
        sd = methods.get(("drawing", "square"), {})
        paired.append({"case": case, "family": meta["family"], "nodes": meta["nodes"], "edges": meta["edges"],
                       "assignment_comparable": lin.get("status")==sq.get("status")=="ok",
                       "drawing_comparable": ld.get("status")==sd.get("status")=="ok",
                       **{f"linear_{k}": lin.get(k, ld.get(k)) for k in ("predicted_dummies","dummy_nodes","max_span","span_sum","span_square_sum","seconds","geometric_crossings","drawing_seconds","geometry_seconds")},
                       **{f"square_{k}": sq.get(k, sd.get(k)) for k in ("predicted_dummies","dummy_nodes","max_span","span_sum","span_square_sum","seconds","geometric_crossings","drawing_seconds","geometry_seconds")}})
    with (output/"paired.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(paired[0]) if paired else ["case"]); writer.writeheader(); writer.writerows(paired)
    summary=[]
    metrics=("dummy_nodes","max_span","seconds","drawing_seconds","geometric_crossings")
    for (n,family), group in group_rows(paired).items():
        row={"nodes":n,"family":family,"trials":len(group),
             "assignment_comparable":sum(x["assignment_comparable"] for x in group),
             "drawing_comparable":sum(x["drawing_comparable"] for x in group)}
        for metric in metrics:
            key=f"{metric}"
            eligible = [x for x in group if x["drawing_comparable"]] if metric in ("drawing_seconds", "geometric_crossings") else [x for x in group if x["assignment_comparable"]]
            diffs=[x.get(f"square_{key}")-x.get(f"linear_{key}") for x in eligible
                   if isinstance(x.get(f"square_{key}"), (int,float)) and isinstance(x.get(f"linear_{key}"),(int,float))]
            row[f"{metric}_diff_median"] = median(diffs) if diffs else None
            row[f"{metric}_decrease"] = sum(d<0 for d in diffs)
            row[f"{metric}_same"] = sum(d==0 for d in diffs)
            row[f"{metric}_increase"] = sum(d>0 for d in diffs)
        summary.append(row)
    with (output/"summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]) if summary else ["nodes"]); writer.writeheader(); writer.writerows(summary)
    (output/"completion.json").write_text(json.dumps({"trials":len(paired),"summary_rows":len(summary)},indent=2)+"\n",encoding="utf-8")


def group_rows(rows):
    result=defaultdict(list)
    for row in rows: result[row["nodes"],row["family"]].append(row)
    return result


if __name__ == "__main__":
    main()
