"""無向の小世界グラフを作り、円環上の短い時計回り方向へ有向化する。"""

import networkx as nx

from .lib.randomness import resolve_seed
from .lib.types import Graph
from .lib.validation import validate_node_count, validate_probability


def generate_watts_strogatz_graph(
    n: int,
    k: int = 4,
    p: float = 0.1,
    seed: int | None = None,
    ensure_connected: bool = True,
    tries: int = 100,
) -> Graph:
    """k 個の近傍を持つ円環の辺を、確率 p で張り替える。

    ensure_connected=True では最大 tries 回まで連結な無向グラフの
    生成を試みる。その各辺を円環上の短い時計回り方向へ向ける。
    p=0 なら円環に沿う有向閉路を持つ。弱連結性は有向化しても保たれる。
    """
    validate_node_count(n, minimum=3)
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0 or k >= n or k % 2:
        raise ValueError("k must be a positive even integer smaller than n")
    validate_probability(p, "p")
    if isinstance(tries, bool) or not isinstance(tries, int) or tries <= 0:
        raise ValueError("tries must be a positive integer")

    # NetworkX に None を渡すとグローバル乱数器を使うため、シードを確定する。
    resolved_seed = resolve_seed(seed)
    if ensure_connected:
        graph = nx.connected_watts_strogatz_graph(
            n=n, k=k, p=p, tries=tries, seed=resolved_seed
        )
    else:
        graph = nx.watts_strogatz_graph(n=n, k=k, p=p, seed=resolved_seed)

    edges = []
    for source, target in graph.edges():
        clockwise_distance = (target - source) % n
        counterclockwise_distance = (source - target) % n
        if clockwise_distance <= counterclockwise_distance:
            edges.append((source, target))
        else:
            edges.append((target, source))

    return list(graph.nodes()), edges
