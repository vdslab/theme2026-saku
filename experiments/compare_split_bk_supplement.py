"""Apply split BK to both saved postprocessed embeddings, as a separate comparison."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from compare_pipeline_postprocessing import (
    CONFIGS, CrossingResult, Graph, measure_geometry, pipeline, prepare, write_csv, write_json,
)
from report_pipeline_postprocessing import GROUPS, paired_stats

METRICS = ("geometric_crossings", "bends", "either_seam_edges", "total_edge_length",
           "dummy_inner_geometric_crossings", "coordinate_seconds")


def run(output):
    root = output / "split_bk"
    root.mkdir(exist_ok=True)
    method = "brandes_koepf_blocks"
    write_json(root / "settings.json", {"coordinate_method": method, "input": "saved final embedding",
                                       "postprocessing_settings": "../settings.json"})
    records = json.loads((output / "inputs.json").read_text())
    rows, pairs = [], []
    for record in records:
        name, family = record["case"], record["family"]
        case = json.loads((output / f"{name}.json").read_text())
        original = Graph(tuple(record["graph"]["nodes"]), tuple(map(tuple, record["graph"]["edges"])))
        outcomes = {}
        if case["shared"] is not None:
            assigned, _ = prepare(original, case["shared"])
            graph = pipeline.insert_dummy_nodes(original, assigned[1])
            paths = {tuple(edge): chain for edge, chain in case["shared"]["chains"]}
        for condition in case["execution_order"] or CONFIGS:
            row = {"case": name, "family": family, "method": condition, "status": "ok"}
            outcomes[condition] = row
            attempts = case["outcomes"][condition].get("attempts", [])
            post = next((a["post"] for a in reversed(attempts) if "post" in a), None)
            if post is None:
                row["status"] = "no_postprocessed_embedding"
                continue
            crossing = CrossingResult({int(layer): nodes for layer, nodes in post["order"].items()},
                                      {(u, v): value for u, v, value in post["winding"]})
            started = perf_counter()
            try:
                coordinates = pipeline.assign_coordinates(graph, crossing, method=method)
            except Exception as error:
                row.update(status="coordinate_error", error_type=type(error).__name__, error=str(error))
            finally:
                row["coordinate_seconds"] = perf_counter() - started
            if row["status"] == "ok":
                try:
                    row.update(measure_geometry(original, graph, paths, crossing, coordinates)["geometry"])
                except Exception as error:
                    row.update(status="geometry_error", error_type=type(error).__name__, error=str(error))
        rows.extend(outcomes.values())
        radial, global_ = (outcomes[condition] for condition in CONFIGS)
        pair = {"case": name, "family": family, "radial_status": radial["status"],
                "global_status": global_["status"]}
        if radial["status"] == global_["status"] == "ok":
            pair.update({metric: global_[metric] - radial[metric] for metric in METRICS})
        pairs.append(pair)
    summary = [{"scope": group, "metric": metric, **paired_stats([
        p[metric] for p in pairs if metric in p and group in ("all", p["family"])
    ])} for group in GROUPS for metric in METRICS]
    write_csv(root, "measurements.csv", rows)
    write_csv(root, "paired.csv", pairs)
    write_csv(root, "summary.csv", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
