"""Count work in one default sifting pass on saved unit-span layouts."""

import argparse
from collections import Counter
import cProfile
import json
from pathlib import Path
from pstats import Stats

from torus_layout.crossing import global_sifting
from torus_layout.crossing.initialization import initial_orders
from torus_layout.crossing.lib.crossings import crossings_between_edges
from torus_layout.models import Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes


def profile(row):
    nodes = tuple(row["graph"]["nodes"])
    edges = tuple(map(tuple, row["graph"]["edges"]))
    ranks = dict(zip(nodes, row["specified_ranks"], strict=True))
    flags = {(u, v): ranks[u] > ranks[v] for u, v in edges}
    proper = insert_dummy_nodes(Graph(nodes, edges), LayerAssignmentResult(ranks, flags, 0))
    if proper.dummy_nodes:
        raise ValueError(f"Expected unit spans in {row['id']}")
    layers = sorted(proper.layers)
    order = initial_orders(proper.layers, layers, list(proper.graph.edges))[0]
    checks = 0

    def count_check():
        nonlocal checks
        checks += 1
        return False

    profiler = cProfile.Profile()
    actual = profiler.runcall(global_sifting.sift_blocks, proper, order, layers, 1,
                              should_stop=count_check)
    if actual != global_sifting.sift_blocks(proper, order, layers, 1):
        raise ValueError(f"Profiling changed the result for {row['id']}")
    stats = Stats(profiler).stats
    widths = Counter(ranks.values())
    candidate_limit = sum(width * width for width in widths.values())
    candidates = checks - len(nodes)
    if not 0 <= candidates <= candidate_limit:
        raise ValueError(f"Candidate count outside singleton-block bound for {row['id']}")

    def calls(function):
        code = function.__code__
        return stats[code.co_filename, code.co_firstlineno, code.co_name][1]

    # In a full single pass, each singleton block contributes one check.
    # Every remaining check corresponds to a candidate about to be scored.
    return {
        "case": row["id"], "seed": row["seed"], "condition": row["width_condition"],
        "blocks": len(nodes), "candidates": candidates,
        "candidate_limit": candidate_limit,
        "strip_scores": calls(global_sifting._strip_score),
        "edge_pair_tests": calls(crossings_between_edges),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    args = parser.parse_args()
    with args.inputs.open(encoding="utf-8") as source:
        for line in source:
            print(json.dumps(profile(json.loads(line))), flush=True)


if __name__ == "__main__":
    main()
