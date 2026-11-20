"""Reproduce the two implementation checks referenced by the consolidated report."""

from argparse import ArgumentParser
import csv
import json
from pathlib import Path
from unittest.mock import patch

from run_torus_study import ROOT, source_fingerprint
from torus_layout.coordinates import api
from torus_layout.coordinates.periodic import drawing_period
from torus_layout.crossing import count_crossings, reduce_crossings
from torus_layout.crossing.lib.crossings import pair_crossings
from torus_layout.crossing.lib.embedding import oriented_pair_embedding
from torus_layout.drawing.preparation import prepare_drawing
from torus_layout.layering.lib.solver import use_local_license
from torus_layout.models import CoordinateResult, CrossingResult, Graph, SubdividedGraph
from torus_study.geometry import crossing_metrics, torus_routes
from torus_study.stages import prepared
from torus_study.validation_inputs import previous_case, read_jsonl


def two_layer_crossing():
    edges = ((0, 3), (2, 1))
    order = {0: [0, 1], 1: [2, 3]}
    graph = Graph((0, 1, 2, 3), edges)
    flags = {edges[0]: False, edges[1]: True}
    sub = SubdividedGraph(graph, order, flags, dict.fromkeys(edges, 1.0), graph.nodes)
    embedding = CrossingResult(order, dict.fromkeys(edges, 0))
    coords = CoordinateResult({0: (0., 0.), 1: (0., 1.), 2: (1., 0.), 3: (1., 1.)}, 2.)
    oriented, winding, _ = oriented_pair_embedding(order, embedding.winding_numbers, 0, 1, list(edges))
    routes, bounds = torus_routes({edge: edge for edge in edges}, sub, embedding, coords)
    return {
        "order": order,
        "edges": [{"source": u, "target": v, "horizontal_wrap": flags[u, v],
                   "vertical_winding": embedding.winding_numbers[u, v]} for u, v in edges],
        "coordinates": coords.positions,
        "period": coords.period,
        "local_crossings": pair_crossings(order, winding, 0, 1, oriented),
        "embedding_crossings": count_crossings(sub, embedding),
        "geometric_crossings": crossing_metrics(routes, bounds)["geometric_crossings"],
    }


def drawing_domains(manifest):
    with use_local_license():
        for record in read_jsonl(manifest):
            case = previous_case(record)
            _, _, sub, _ = prepared(case.graph)
            embedding = reduce_crossings(sub)
            minimum = drawing_period(embedding.order, 1.)
            for factor in (1., 1.25, 1.6):
                for method, weight in (("brandes_koepf", 0), ("torus_lp", 0), ("torus_lp", 1)):
                    with patch.object(api, "drawing_period", return_value=minimum * factor):
                        coords = api.assign_coordinates(sub, embedding, method=method, bend_weight=weight)
                    status = "ok"
                    try:
                        prepare_drawing(
                            list(case.graph.nodes), list(sub.graph.edges), sub.layers,
                            order=embedding.order, psi=embedding.winding_numbers, t_val=sub.torus_flags,
                            pos=coords.positions, vertical_period=coords.period, show=False,
                        )
                    except ValueError as error:
                        if "lies outside the vertical domain" not in str(error):
                            raise
                        status = "outside_vertical_domain"
                    yield {
                        "case": case.id, "method": method, "bend_weight": weight,
                        "period_factor": factor, "period": coords.period, "status": status,
                    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--inputs", type=Path, default=(
        ROOT / "output/torus_validation_20261120/coordinate_audit/inputs.jsonl"
    ))
    args = parser.parse_args()
    rows = list(drawing_domains(args.inputs))
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "drawing_domain.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    records = {
        "two_layer_crossing.json": two_layer_crossing(),
        "settings.json": {
            "source_sha256": source_fingerprint(),
            "coordinate_domain_input": str(args.inputs.relative_to(ROOT) if args.inputs.is_relative_to(ROOT)
                                           else args.inputs),
            "local_license": True,
            "period_factors": [1, 1.25, 1.6],
            "minimum_node_gap": 1,
            "render_entry_point": "torus_layout.drawing.preparation.prepare_drawing",
            "solver_budget_override": None,
        },
    }
    for filename, record in records.items():
        (args.output / filename).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
