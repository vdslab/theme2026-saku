"""Reproducible fixed-embedding comparison; no layer optimization confound.

PYTHONPATH=src ./theme2026-saku/bin/python experiments/evaluate_coordinate_methods.py --local-solver
The explicit local flag uses the installed local Gurobi license for small cases.
Without it, the application's .env WLS configuration is used.
"""
import argparse
import csv
from pathlib import Path
import random
from time import perf_counter
import math
import gurobipy as gp
from torus_layout.models import Graph, LayerAssignmentResult
from torus_layout.subdivision import insert_dummy_nodes
from torus_layout.crossing import reduce_crossings
from torus_layout.coordinates import assign_coordinates, optimization


def measure(graph, crossing, result):
    delta = {(u, v): result.positions[v][1] - result.positions[u][1]
             + crossing.winding_numbers.get((u, v), 0) * result.period
             for u, v in graph.graph.edges}
    bends = []
    for node in graph.dummy_nodes:
        incoming = [e for e in delta if e[1] == node]
        outgoing = [e for e in delta if e[0] == node]
        if len(incoming) == len(outgoing) == 1:
            bends.append(delta[outgoing[0]] - delta[incoming[0]])
    return dict(l1=sum(abs(d) for d in delta.values()),
                l2=sum(d*d for d in delta.values()),
                length=sum(math.hypot(1, d) for d in delta.values()),
                bend2=sum(b*b for b in bends),
                max_displacement=max(map(abs, delta.values()), default=0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-solver', action='store_true')
    parser.add_argument('--draw', action='store_true', help='save four n=24, seed=0 examples')
    parser.add_argument('--output', default='experiments/results/coordinate_methods.csv')
    args = parser.parse_args()
    if args.local_solver:
        optimization.create_gurobi_env = lambda: gp.Env(params={'OutputFlag': 0})
    rows = []
    for n in (12, 24, 48):
        for seed in range(5):
            rng = random.Random(seed)
            ranks = {i: i % 4 for i in range(n)}
            edges = tuple((u, v) for u in ranks for v in ranks
                          if ranks[u] != ranks[v] and rng.random() < 2/n)
            graph = insert_dummy_nodes(Graph(tuple(ranks), edges), LayerAssignmentResult(
                ranks, {e: ranks[e[0]] > ranks[e[1]] for e in edges}, 0))
            crossing = reduce_crossings(graph, rounds=1)
            for method, bend_weight in [('brandes_koepf', 0), ('torus_qp', 0),
                                        ('torus_qp', 1), ('torus_lp', 0)]:
                start = perf_counter()
                result = assign_coordinates(graph, crossing, method=method, bend_weight=bend_weight)
                elapsed = perf_counter() - start
                if args.draw and n == 24 and seed == 0:
                    from torus_layout.drawing import draw_layout
                    draw_layout(graph, crossing, result,
                                save_path=f'experiments/results/coordinates_{method}_{bend_weight}.png',
                                show=False)
                rows.append(dict(n=n, seed=seed, vertices=len(graph.graph.nodes),
                                 segments=len(graph.graph.edges), method=method,
                                 bend_weight=bend_weight, seconds=elapsed,
                                 **measure(graph, crossing, result)))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for method, bend_weight in [('torus_qp', 0), ('torus_qp', 1), ('torus_lp', 0)]:
        selected = [r for r in rows if r['method'] == method and r['bend_weight'] == bend_weight]
        baseline = [r for r in rows if r['method'] == 'brandes_koepf']
        print(method, bend_weight, {key: round(sum(r[key] for r in selected) /
              sum(r[key] for r in baseline), 4) for key in ('l1', 'l2', 'length', 'bend2')},
              'median_seconds', sorted(r['seconds'] for r in selected)[len(selected)//2])


if __name__ == '__main__':
    main()
