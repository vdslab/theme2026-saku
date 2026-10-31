"""自己ループと既存の辺を除いた候補へ、確率的に有向辺を追加する。"""

import random

from .types import Edge


def add_random_edges(
    vertices: list[int],
    edges: list[Edge],
    edge_prob: float,
    rng: random.Random,
) -> None:
    """頂点番号順に候補を評価し、渡された辺リストへ追記する。

    既存実装と同じ候補順・乱数の消費順を維持する。逆向きの辺は
    別の候補として扱うため、双方向の辺が生じることもある。
    """
    existing_edges = set(edges)
    for source in vertices:
        for target in vertices:
            edge = (source, target)
            if source != target and edge not in existing_edges:
                if rng.random() < edge_prob:
                    edges.append(edge)
                    existing_edges.add(edge)
