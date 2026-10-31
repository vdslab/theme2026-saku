"""スパニングツリーで弱連結性を確保し、ランダムな有向辺を加える。"""

from .lib.edges import add_random_edges
from .lib.randomness import create_random
from .lib.types import Graph
from .lib.validation import validate_node_count, validate_probability


def generate_random_connected_graph(
    n: int, edge_prob: float = 0.3, seed: int | None = None
) -> Graph:
    """n 頂点の弱連結な有向グラフを返す。

    既訪問頂点から未訪問頂点への辺で木を作り、その後すべての
    未使用の有向辺を edge_prob の確率で追加する。閉路は許容する。
    """
    validate_node_count(n)
    validate_probability(edge_prob, "edge_prob")
    rng, _ = create_random(seed)
    vertices = list(range(n))
    edges = []
    if not vertices:
        return vertices, edges

    visited = {vertices[0]}
    unvisited = set(vertices[1:])
    while unvisited:
        source = rng.choice(list(visited))
        target = rng.choice(list(unvisited))
        edges.append((source, target))
        visited.add(target)
        unvisited.remove(target)

    add_random_edges(vertices, edges, edge_prob, rng)
    return vertices, edges
