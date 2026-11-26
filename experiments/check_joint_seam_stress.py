"""Check joint DP against exhaustive cut search on saved long-edge inputs."""

import argparse
import json
from math import prod
from pathlib import Path
from random import Random

from benchmark_joint_seam import exhaustive
from torus_layout.crossing import count_crossings, optimize_joint_seam, reduce_crossings
from torus_layout.crossing.seam import seam_score
from torus_layout.models import CrossingResult, Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes


def evaluate(row):
    nodes = tuple(row["graph"]["nodes"])
    edges = tuple(map(tuple, row["graph"]["edges"]))
    ranks = dict(zip(nodes, row["specified_ranks"], strict=True))
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    sub = insert_dummy_nodes(Graph(nodes, edges), LayerAssignmentResult(ranks, flags, 0))
    if len(sub.layers) != 4:
        raise ValueError("Expected a four-layer stress input")

    rng = Random(row["seed"])
    order = {layer: list(members) for layer, members in sub.layers.items()}
    for members in order.values():
        rng.shuffle(members)
    winding = {edge: rng.randrange(-2, 3) for edge in sub.graph.edges}
    starts = {
        "randomized": CrossingResult(order, winding),
        "global_sifting": reduce_crossings(sub, unwind=False, optimize_seams=False, algo2=False),
    }
    for condition, start in starts.items():
        oracle = exhaustive(sub, start)
        joint = optimize_joint_seam(sub, start)
        score = None if joint is None else seam_score(sub, joint, True)
        before = count_crossings(sub, start)
        after = None if joint is None else count_crossings(sub, joint)
        yield {
            "case": row["id"], "seed": row["seed"], "condition": condition,
            "nodes": len(nodes), "edges": len(edges), "layers": len(sub.layers),
            "dummy_nodes": len(sub.dummy_nodes),
            "cut_combinations": prod(map(len, start.order.values())),
            "initial_score": seam_score(sub, start, True),
            "exhaustive_score": oracle, "joint_score": score,
            "optimality_gap": None if oracle is None or score is None else score[1] - oracle[1],
            "crossings_before": before, "crossings_after": after,
            "agrees": score == oracle and (after is None or after == before),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    args = parser.parse_args()
    failures = 0
    with args.inputs.open(encoding="utf-8") as source:
        for row in map(json.loads, source):
            for result in evaluate(row):
                print(json.dumps(result), flush=True)
                failures += not result["agrees"]
    if failures:
        raise SystemExit(f"{failures} joint DP checks disagreed")


if __name__ == "__main__":
    main()
