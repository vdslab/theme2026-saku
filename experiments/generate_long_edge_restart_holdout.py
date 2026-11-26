"""Emit new fixed-rank cyclic graphs with prescribed long-edge counts."""

import json
from itertools import product
from random import Random


def main():
    nodes = tuple(range(12))
    ranks = tuple(u % 4 for u in nodes)
    cycle = [(u, (u + 1) % len(nodes)) for u in nodes]
    possible = {
        span: [(u, v) for u, v in product(nodes, repeat=2) if (ranks[v] - ranks[u]) % 4 == span]
        for span in (2, 3)
    }
    for seed in range(1201, 1225):
        rng = Random(seed)
        edges = sorted(cycle + rng.sample(possible[2], 8) + rng.sample(possible[3], 4))
        print(json.dumps({
            "id": f"long-edge-restart-holdout-{seed}", "seed": seed,
            "graph": {"nodes": nodes, "edges": edges}, "specified_ranks": ranks,
        }))


if __name__ == "__main__":
    main()
