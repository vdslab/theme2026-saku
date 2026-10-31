"""複数の有向閉路をつなぎ、残りの頂点とランダムな辺を追加する。"""

from .lib.edges import add_random_edges
from .lib.randomness import create_random
from .lib.types import Graph, SeededGraph
from .lib.validation import validate_node_count, validate_probability


def generate_cyclic_graph(
    n: int,
    num_cycles: int = 2,
    edge_prob: float = 0.2,
    seed: int | None = None,
    *,
    return_seed: bool = False,
) -> Graph | SeededGraph:
    """長さ3以上の閉路を配置した弱連結グラフを返す。

    num_cycles は配置を試みる閉路数。頂点が足りないときは実際に
    作れた閉路だけをつなぐ。残りの頂点は閉路上の頂点と双方向に
    接続する。追加辺によって閉路総数が num_cycles を超える場合もある。
    return_seed=True なら戻り値の末尾に使用したシードを付ける。
    """
    validate_node_count(n, minimum=3)
    validate_probability(edge_prob, "edge_prob")
    if (
        isinstance(num_cycles, bool)
        or not isinstance(num_cycles, int)
        or num_cycles <= 0
    ):
        raise ValueError("num_cycles must be a positive integer")

    rng, resolved_seed = create_random(seed)
    vertices = list(range(n))
    edges = []
    cycles = []
    nodes_per_cycle = max(3, n // num_cycles)
    next_node = 0

    for _ in range(num_cycles):
        cycle_nodes = vertices[next_node : next_node + nodes_per_cycle]
        if len(cycle_nodes) < 3:
            break
        cycles.append(cycle_nodes)
        edges.extend(zip(cycle_nodes, cycle_nodes[1:] + cycle_nodes[:1]))
        next_node += len(cycle_nodes)

    for vertex in vertices[next_node:]:
        target = rng.randint(0, next_node - 1)
        edges.extend([(target, vertex), (vertex, target)])

    for first_cycle, second_cycle in zip(cycles, cycles[1:]):
        edges.append((rng.choice(first_cycle), rng.choice(second_cycle)))

    add_random_edges(vertices, edges, edge_prob, rng)
    if return_seed:
        return vertices, edges, resolved_seed
    return vertices, edges
