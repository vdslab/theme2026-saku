"""Compare distinct insertion orders for saved fixed-rank inputs."""

import argparse
import json
from collections import Counter
from functools import partial
from pathlib import Path
from unittest.mock import patch

from torus_layout import pipeline
from torus_layout.coordinates import assign_coordinates
from torus_layout.coordinates.blocks import UnsplitBlockOrderError
from torus_layout.crossing import api as crossing_api
from torus_layout.crossing.global_sifting import _trial_orders, sift_blocks
from torus_layout.crossing.initialization import initial_orders
from torus_layout.models import Graph, LayerAssignmentResult, LayerSearchResult, PipelineConfig
from torus_layout.subdivision import build_dummy_blocks, insert_dummy_nodes
from torus_study.geometry import route_metrics, torus_routes
from torus_study.stages import subdivision_metrics


def audit(row, rounds=0):
    nodes = tuple(row["graph"]["nodes"])
    edges = tuple(map(tuple, row["graph"]["edges"]))
    if "specified_ranks" in row:
        ranks = dict(zip(nodes, row["specified_ranks"], strict=True))
    else:
        ranks = {node: node // row["layer_width"] for node in nodes}
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    graph = Graph(nodes, edges)
    assignment = LayerAssignmentResult(ranks, flags, 0)
    proper = insert_dummy_nodes(graph, assignment)
    layers = sorted(proper.layers)
    initial = initial_orders(proper.layers, layers, list(proper.graph.edges))[0]
    blocks = build_dummy_blocks(proper)
    node_block = {node: block for block, members in enumerate(blocks) for node in members}
    sequence = list(dict.fromkeys(node_block[node] for layer in initial.values() for node in layer))
    rank = {block: i for i, block in enumerate(sequence)}
    order = {layer: sorted(initial[layer], key=lambda node: rank[node_block[node]]) for layer in layers}
    positions = [{} for _ in blocks]
    for layer, members in order.items():
        for node in members:
            positions[node_block[node]][layer] = node
    layer_blocks = {layer: {node_block[node] for node in order[layer]} for layer in layers}

    counts = Counter()
    for block in sequence:
        affected = positions[block]
        remaining = [member for member in sequence if member != block]
        expected = len(set().union(*(layer_blocks[layer] for layer in affected)))
        dense = _trial_orders(order, affected, block, remaining, node_block, False)
        sparse = _trial_orders(order, affected, block, remaining, node_block, True)
        incremental = _trial_orders(order, affected, block, remaining, node_block, True, True)
        actual = 0
        for full, reduced, delta in zip(dense, sparse, incremental, strict=True):
            if full != reduced or full != delta:
                raise ValueError(f"Insertion order mismatch for {row['id']}, block {block}")
            actual += 1
        if actual != expected:
            raise ValueError(f"Expected {expected} candidates for {row['id']}, block {block}")
        counts[len(affected)] += actual
    result = {"case": row["id"], "blocks": len(blocks),
              "blocks_by_layer_count": dict(Counter(map(len, positions))),
              "candidates": sum(counts.values()), "candidates_by_layer_count": dict(counts)}
    if rounds:
        reference = sift_blocks(proper, initial, layers, rounds)
        embedding = crossing_api.reduce_crossings(proper, rounds=rounds)
        coordinates = assign_coordinates(proper, embedding, method="brandes_koepf_blocks")
        for incremental in (False, True):
            sift = partial(sift_blocks, sparse_candidates=True,
                           incremental_orders=incremental, incremental_scores=incremental)
            actual = sift(proper, initial, layers, rounds)
            if actual != reference:
                raise ValueError(f"Final order or winding mismatch for {row['id']}, {rounds} passes")
            with patch.object(crossing_api, "sift_blocks", sift):
                alternative = crossing_api.reduce_crossings(proper, rounds=rounds)
            if (alternative != embedding or
                assign_coordinates(proper, alternative, method="brandes_koepf_blocks") != coordinates):
                raise ValueError(f"Final drawing mismatch for {row['id']}")
        paths, _ = subdivision_metrics(graph, proper)
        routes, bounds = torus_routes(paths, proper, embedding, coordinates)
        result.update(round_limit=rounds, equal_order_and_winding=True, equal_drawing=True,
                      geometry=route_metrics(routes, bounds))
        configuration = LayerSearchResult(len(layers), sum(flags.values()), 0)
        config = PipelineConfig(rounds=rounds)
        outcomes = []
        with patch.object(pipeline, "assign_layers", return_value=(configuration, assignment)):
            for sparse, incremental in ((False, False), (True, False), (True, True)):
                sift = partial(sift_blocks, sparse_candidates=sparse,
                               incremental_orders=incremental, incremental_scores=incremental)
                try:
                    with patch.object(crossing_api, "sift_blocks", sift):
                        layout = pipeline.run_pipeline(graph, config)
                except UnsplitBlockOrderError as error:
                    outcomes.append(("unsplit_order_error", str(error)))
                else:
                    outcomes.append((layout.seam_method_used, layout.crossing, layout.coordinates))
        if any(outcome != outcomes[0] for outcome in outcomes[1:]):
            raise ValueError(f"Default pipeline outcome mismatch for {row['id']}")
        result.update(default_pipeline_outcome=outcomes[0][0], equal_default_pipeline=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("cases", nargs="*", help="Audit these IDs, or all rows if omitted")
    parser.add_argument("--rounds", type=int, default=0, help="Also compare full sifting with this pass limit")
    args = parser.parse_args()
    if args.rounds < 0:
        parser.error("round limit must be nonnegative")
    with args.inputs.open(encoding="utf-8") as source:
        rows = {row["id"]: row for row in map(json.loads, source)}
    for case in args.cases or rows:
        print(json.dumps(audit(rows[case], args.rounds)), flush=True)


if __name__ == "__main__":
    main()
