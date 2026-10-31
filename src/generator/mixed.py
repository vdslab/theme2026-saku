"""確率で選んだ閉路部分と、残りのDAG部分をつないだグラフを作る。"""

from .lib.connectivity import is_connected
from .lib.randomness import create_random
from .lib.types import Graph
from .lib.validation import validate_node_count, validate_probability


def generate_mixed_graph(
    n: int,
    edge_prob: float = 0.3,
    cycle_prob: float = 0.3,
    seed: int | None = None,
) -> Graph:
    """各頂点を cycle_prob の確率で閉路部分に割り当てる。

    選ばれた頂点が3個以上なら有向閉路を作る。残りには昇順の辺を
    edge_prob の確率で追加する。両部分があれば相互に辺を追加し、
    最後に弱連結になるまで番号の隣り合う頂点を結ぶ。
    """
    validate_node_count(n)
    validate_probability(edge_prob, "edge_prob")
    validate_probability(cycle_prob, "cycle_prob")
    rng, _ = create_random(seed)
    vertices = list(range(n))
    edges = []

    cycle_nodes = [vertex for vertex in vertices if rng.random() < cycle_prob]
    cycle_node_set = set(cycle_nodes)
    dag_nodes = [vertex for vertex in vertices if vertex not in cycle_node_set]

    if len(cycle_nodes) >= 3:
        edges.extend(zip(cycle_nodes, cycle_nodes[1:] + cycle_nodes[:1]))

    for index, source in enumerate(dag_nodes):
        for target in dag_nodes[index + 1 :]:
            if rng.random() < edge_prob:
                edges.append((source, target))

    if dag_nodes and cycle_nodes:
        edges.append((rng.choice(dag_nodes), rng.choice(cycle_nodes)))
        edges.append((rng.choice(cycle_nodes), rng.choice(dag_nodes)))

    # 既存実装の補完順を維持する。すでにある辺が再び追加される場合もある。
    if not is_connected(vertices, edges):
        for source in range(n - 1):
            if is_connected(vertices, edges):
                break
            edges.append((source, source + 1))

    return vertices, edges
