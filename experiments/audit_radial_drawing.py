"""Compare the radial implementation and the shared evaluator on fixed inputs."""

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from math import ceil, dist, floor, isclose, tau
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from radial_layout import (
    assign_coordinates, assign_layers, count_crossings, insert_dummy_nodes,
    reduce_crossings, remove_cycles,
)
from radial_layout.drawing import draw_radial_graph
from radial_layout.random_graph import generate_watts_strogatz_digraph
from torus_study.framework import repository_baseline

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "output" / "torus_goal_20261126"
PICTURES = {
    "two-rings", "reciprocal", "wide-inner-ring", "ws-20-4-1", "ws-20-4-11", "ws-20-8-0",
    "ws-20-8-7", "dag-18-2-0", "scc_chain-24-2-3", "sampson-time-1", "UKfaculty-induced-2",
}


def cases():
    yield "two-rings", tuple(range(7)), ((0, 3), (0, 4), (1, 4), (1, 5), (2, 5), (2, 3))
    yield "reciprocal", tuple(range(5)), ((0, 1), (1, 0), (1, 2), (2, 3), (3, 4), (0, 4))
    yield "wide-inner-ring", tuple(range(31)), tuple((u, 30) for u in range(30))
    for size, neighbors, seeds in ((10, 4, (0, 7)), (20, 4, range(12)), (20, 8, (0, 7)), (35, 4, (0, 9))):
        for seed in seeds:
            nodes, edges = generate_watts_strogatz_digraph(
                size=size, seed=seed, neighbor_count=neighbors, rewiring_probability=0.3,
            )
            yield f"ws-{size}-{neighbors}-{seed}", nodes, edges
    for group in ("framework", "public"):
        for line in (MANIFEST / group / "inputs.jsonl").read_text().splitlines():
            row = json.loads(line)
            graph = row["graph"]
            yield row["id"], tuple(graph["nodes"]), tuple(map(tuple, graph["edges"]))


def exact_crossings(hierarchy, coordinates, multiplicities):
    """Count integer-angle coincidences strictly between the two radii."""
    bands = defaultdict(list)
    original_edge = {
        segment: edge for edge, chain in hierarchy.chains.items() for segment in zip(chain, chain[1:])
    }
    max_turns = 0.0
    for (u, v), winding in coordinates.winding.items():
        radius, start = coordinates.polar[u]
        _, end = coordinates.polar[v]
        if radius > 0:
            a, b = start / tau, end / tau + winding
            bands[radius].append((a, b, original_edge[u, v]))
            max_turns = max(max_turns, abs(b - a))
    count = directed_count = 0
    crossing_pairs = set()
    for band in bands.values():
        for (a, b, edge), (c, d, other) in combinations(band, 2):
            lower, upper = sorted((a - c, b - d))
            events = max(0, ceil(upper - 1e-10) - floor(lower + 1e-10) - 1)
            if events:
                crossing_pairs.add(tuple(sorted((edge, other))))
                count += events
                directed_count += events * multiplicities[edge] * multiplicities[other]
    inner = [edge for edge in hierarchy.edges if set(edge) <= hierarchy.dummy_nodes]
    aligned = all(
        abs(coordinates.polar[v][1] - coordinates.polar[u][1]) < 1e-9
        and coordinates.winding[u, v] == 0
        for u, v in inner
    )
    return {
        "exact_spiral_crossings": count,
        "exact_directed_crossings": directed_count,
        "exact_directed_crossing_pairs": sum(multiplicities[e] * multiplicities[f] for e, f in crossing_pairs),
        "exact_max_segment_turns": max_turns,
        "inner_segments": len(inner),
        "inner_segments_aligned": aligned,
    }


def measure(name, nodes, edges, output):
    result = {"case": name, "nodes": len(nodes), "edges": len(edges)}
    edge_set = set(edges)
    result["reciprocal_pairs"] = sum(edge[::-1] in edge_set for edge in edges) // 2
    start = perf_counter()
    metrics, (routes, _) = repository_baseline(SimpleNamespace(nodes=nodes, edges=edges), radial=True)
    result.update(metrics, layout_and_measurement_seconds=perf_counter() - start)
    dag = remove_cycles(nodes, edges)
    layout_edges = tuple(dict.fromkeys(dag.edges))
    hierarchy = insert_dummy_nodes(nodes, layout_edges, assign_layers(nodes, layout_edges))
    embedding = reduce_crossings(hierarchy.layers, hierarchy.edges)
    coords = assign_coordinates(embedding)
    multiplicities = Counter(e[::-1] if e in dag.reversed_edges else e for e in edges)
    result.update(exact_crossings(hierarchy, coords, multiplicities))
    result.update(
        crossings_before=count_crossings(hierarchy.layers, hierarchy.edges),
        correct_route_endpoints=all(
            dist(route.points[0], coords.cartesian[route.edge[0]]) < 1e-9
            and dist(route.points[-1], coords.cartesian[route.edge[1]]) < 1e-9
            for route in routes
        ) and {route.edge for route in routes} == edge_set,
    )
    if name in PICTURES:
        start = perf_counter()
        draw_radial_graph(nodes, edges, coords.cartesian, coords.polar, coords.radii,
                          hierarchy.chains, coords.winding, dag.reversed_edges,
                          save_path=output / f"{name}.png", show=False)
        result["render_seconds"] = perf_counter() - start
    return result


def verify(row):
    checks = {
        "centerline crossings": row["combinatorial_crossings"]
        == row["exact_spiral_crossings"] == row["geometric_crossings_on_layout_edges"],
        "directed crossings": row["geometric_crossings"] == row["exact_directed_crossings"],
        "directed crossing pairs": row["crossing_edge_pairs"] == row["exact_directed_crossing_pairs"],
        "shared routes": row["overlapping_edge_pairs"] == row["reciprocal_pairs"],
        "touches": row["contact_events"] == 0,
        "route endpoints": row["correct_route_endpoints"],
        "long edge alignment": row["inner_segments_aligned"] and row["max_bends_per_edge"] <= 2,
        "crossing reduction": row["combinatorial_crossings"] <= row["crossings_before"],
        "maximum turn": isclose(row["max_segment_turns"], row["exact_max_segment_turns"], abs_tol=1e-10),
    }
    return [name for name, passed in checks.items() if not passed]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", action="append")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    failed = False
    with (args.output / "measurements.jsonl").open("x") as file:
        for name, nodes, edges in cases():
            if args.case and name not in args.case:
                continue
            try:
                row = measure(name, nodes, edges, args.output)
                errors = verify(row) if args.verify else []
                row["status"] = "invalid_metrics" if errors else "ok"
                if errors:
                    row["errors"] = errors
            except Exception as error:
                row = {"case": name, "status": type(error).__name__, "error": str(error)}
            print(name, row["status"], flush=True)
            failed |= row["status"] != "ok"
            file.write(json.dumps(row, allow_nan=False) + "\n")
            file.flush()
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
