"""描画例で使用する Watts--Strogatz グラフを生成する。"""

import random

import networkx as nx

DEFAULT_REWIRING_PROBABILITY = 0.25
DEFAULT_NEIGHBOR_COUNT = 4


def generate_watts_strogatz_digraph(
    size: int,
    seed: int,
    *,
    neighbor_count: int | None = None,
    rewiring_probability: float = DEFAULT_REWIRING_PROBABILITY,
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    """NetworkXで Watts--Strogatz グラフを生成し、辺をランダムに方向付けする。

    ``networkx.watts_strogatz_graph`` で無向のスモールワールド構造を生成する。
    その後、同じシードを使って各無向辺を再現可能な方法で方向付けする。
    得られた有向グラフには循環が含まれる可能性があるため、循環除去は意図的に
    杉山フレームワークの最初の段階へ委ねる。
    """

    if size < 3:
        raise ValueError("Watts--Strogatz グラフの生成には size >= 3 が必要です")
    if not 0.0 <= rewiring_probability <= 1.0:
        raise ValueError("rewiring_probability は0以上1以下である必要があります")

    resolved_neighbors = _resolve_neighbor_count(size, neighbor_count)
    graph = nx.watts_strogatz_graph(
        n=size,
        k=resolved_neighbors,
        p=rewiring_probability,
        seed=seed,
    )

    rng = random.Random(seed)
    directed_edges = []
    for first, second in sorted(graph.edges()):
        if rng.random() < 0.5:
            directed_edges.append((first, second))
        else:
            directed_edges.append((second, first))

    return tuple(graph.nodes()), tuple(directed_edges)


def _resolve_neighbor_count(size: int, neighbor_count: int | None) -> int:
    if neighbor_count is None:
        neighbor_count = min(DEFAULT_NEIGHBOR_COUNT, size - 1)
        if neighbor_count % 2:
            neighbor_count -= 1
    if neighbor_count < 2:
        raise ValueError("neighbor_count は2以上である必要があります")
    if neighbor_count >= size:
        raise ValueError("neighbor_count は size より小さい必要があります")
    if neighbor_count % 2:
        raise ValueError("neighbor_count は偶数である必要があります")
    return neighbor_count
