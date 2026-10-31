"""頂点番号の昇順にだけ辺を向け、弱連結な有向非巡回グラフを作る。"""

from .lib.connectivity import is_connected
from .lib.randomness import create_random
from .lib.types import Graph
from .lib.validation import validate_node_count, validate_probability


def generate_dag(
    n: int, edge_prob: float = 0.3, seed: int | None = None
) -> Graph:
    """小さい番号から大きい番号へ確率的に辺を追加する。

    非連結なら隣接番号を結ぶ鎖の不足辺を追加する。すべての辺で
    source < target が成り立つため、連結補完後も閉路は生じない。
    """
    validate_node_count(n)
    validate_probability(edge_prob, "edge_prob")
    rng, _ = create_random(seed)
    vertices = list(range(n))
    edges = [
        (source, target)
        for source in vertices
        for target in vertices
        if source < target and rng.random() < edge_prob
    ]

    if not is_connected(vertices, edges):
        existing_edges = set(edges)
        for source in range(n - 1):
            edge = (source, source + 1)
            if edge not in existing_edges:
                edges.append(edge)

    return vertices, edges
