"""Re-render selected completed pairs as presentation-sized comparison figures."""

import argparse
import csv
import json
import sys
from pathlib import Path
from unittest.mock import patch

from run_torus_study import ROOT
from compare_layer_balance_large import save_pair
sys.path.insert(0, str(ROOT / "src"))

from torus_layout import pipeline
from torus_layout.layering import balance_layers
from torus_layout.models import Graph, LayerSearchResult, PipelineConfig
from torus_study.geometry import route_metrics, torus_routes
from torus_study.stages import assignment_metrics, record_solver, subdivision_metrics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--case",action="append",required=True)
    parser.add_argument("--solver-seconds",type=float,default=4.0)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    folder=ROOT/"output/torus_balance_diff_square_20261126"
    inputs={r["case"]:r for r in map(json.loads,(folder/"inputs.jsonl").read_text().splitlines())}
    with (folder/"input_completion.csv").open(encoding="utf-8",newline="") as f:
        completed={r["case"]:r for r in csv.DictReader(f)}
    with (folder/"rows.jsonl").open(encoding="utf-8") as f:
        records=[json.loads(line) for line in f]
    searches={r["case"]:r for r in records if r.get("stage")=="search" and r.get("status")=="ok"}
    manifests=[]
    for case_id in args.case:
        item=inputs[case_id]
        search_row=searches[case_id]
        graph=Graph(tuple(range(item["nodes"])),tuple(map(tuple,item["edge_list"])))
        search=LayerSearchResult(search_row["layers"],search_row["wraps"],search_row["seconds"])
        results={}
        for name,method in (("linear","diff"),("square","diff_square")):
            solver_trace=[]
            with record_solver(argparse.Namespace(local_license=True,solver_seconds=args.solver_seconds),solver_trace):
                assignment=balance_layers(graph,search.torus_count,search.layer_count,method)
            stats=assignment_metrics(graph,assignment,search.layer_count,search.torus_count)
            if stats["assignment_violations"]:
                raise ValueError(f"Invalid replayed assignment: {case_id} {name}")
            config=PipelineConfig()
            with patch.object(pipeline,"assign_layers",return_value=(search,assignment)):
                layout=pipeline.run_pipeline(graph,config)
            paths,submetrics=subdivision_metrics(graph,layout.subdivided)
            if (submetrics["unit_span_violations"] or
                    submetrics["dummy_nodes"]!=stats["predicted_dummies"]):
                raise ValueError(f"Invalid replayed subdivision: {case_id} {name}")
            routes,bounds=torus_routes(paths,layout.subdivided,layout.crossing,layout.coordinates)
            geometry=route_metrics(routes,bounds)
            results[name]={"pipeline":layout,"search":search,"dummy_nodes":submetrics["dummy_nodes"],
                           "max_span":stats["max_span"],
                           "geometric_crossings":geometry["geometric_crossings"],
                           "bends":geometry["bends"]}
        save_pair(case_id,item["family"],results,args.output)
        manifests.append({"case":case_id,"family":item["family"],"nodes":item["nodes"],
                          "edges":item["edges"],"layers":search.layer_count,
                          "wraps":search.torus_count,
                          "linear_dummy":results["linear"]["dummy_nodes"],
                          "square_dummy":results["square"]["dummy_nodes"],
                          "linear_max_span":results["linear"]["max_span"],
                          "square_max_span":results["square"]["max_span"],
                          "linear_crossings":results["linear"]["geometric_crossings"],
                          "square_crossings":results["square"]["geometric_crossings"],
                          "linear_bends":results["linear"]["bends"],
                          "square_bends":results["square"]["bends"],
                          "fallback_linear":results["linear"]["pipeline"].seam_method_used=="legacy",
                          "fallback_square":results["square"]["pipeline"].seam_method_used=="legacy"})
    with (args.output/"examples.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(manifests[0])); writer.writeheader();writer.writerows(manifests)


if __name__=="__main__":
    main()
