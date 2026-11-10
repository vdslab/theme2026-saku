"""Seeded Watts–Strogatz generation with random edge orientation."""

import random

import networkx as nx

DEFAULT_NEIGHBOR_COUNT = 4
DEFAULT_REWIRING_PROBABILITY = 0.25


def generate_watts_strogatz_digraph(
    size: int,
    seed: int | None,
    *,
    neighbor_count: int | None = None,
    rewiring_probability: float = DEFAULT_REWIRING_PROBABILITY,
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    """Generate a small-world graph and orient every edge reproducibly."""

    if size < 3:
        raise ValueError("Watts--Strogatz generation requires size >= 3")
    if not 0.0 <= rewiring_probability <= 1.0:
        raise ValueError("rewiring_probability must be between 0 and 1")

    resolved_neighbors = _resolve_neighbor_count(size, neighbor_count)
    graph = nx.watts_strogatz_graph(
        n=size,
        k=resolved_neighbors,
        p=rewiring_probability,
        seed=seed,
    )
    rng = random.Random(seed)
    edges = tuple(
        (first, second) if rng.random() < 0.5 else (second, first)
        for first, second in sorted(graph.edges())
    )
    return tuple(graph.nodes()), edges


def _resolve_neighbor_count(size: int, neighbor_count: int | None) -> int:
    if neighbor_count is None:
        neighbor_count = min(DEFAULT_NEIGHBOR_COUNT, size - 1)
        if neighbor_count % 2:
            neighbor_count -= 1
    if neighbor_count < 2:
        raise ValueError("neighbor_count must be at least 2")
    if neighbor_count >= size:
        raise ValueError("neighbor_count must be smaller than size")
    if neighbor_count % 2:
        raise ValueError("neighbor_count must be even")
    return neighbor_count

