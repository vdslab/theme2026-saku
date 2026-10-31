"""元実装と同じ順序・IDで長距離辺を分割する。"""

from .models import (
    Graph,
    Node,
    Edge,
    Layers,
    Flags,
    Weights,
    LayerAssignmentResult,
    SubdividedGraph,
)


def _insert_dummy_node(
    V: list[Node],
    A: list[Edge],
    L: Layers,
    t_val: Flags | None = None,
    w: Weights | None = None,
) -> tuple[list[Node], list[Edge], Layers, Flags, Weights]:
    """
    平坦トーラス上の階層グラフに対して、長距離エッジを分割するダミーノードを挿入する共通処理。
    必ず左から右（順方向）へエッジが進むように分割し、トーラス境界をまたぐセグメントを判定する。

    Args:
        V: 元のノード集合 list[int]
        A: 元のエッジ集合 list[tuple[int, int]]
        L: 元のレイヤー集合 dict[int: list[int]]
        t_val: トーラス辺フラグ dict[(int,int): bool] (デフォルト: 空のdict)
        w: エッジ重み dict[(int,int): float] (デフォルト: すべて1)

    Returns:
        (new_V, new_A, new_L, new_t_val, new_w):
            - new_V: ダミーノード追加後のノード集合 list[int]
            - new_A: ダミー挿入後のエッジリスト list[tuple(int, int)]
            - new_L: ダミー挿入後のレイヤー辞書 dict[int: list[int]]
            - new_t_val: ダミー挿入後のトーラスフラグ dict[(int,int): bool]
            - new_w: ダミー挿入後のエッジ重み dict[(int,int): float]
    """
    if t_val is None:
        t_val = {}
    if w is None:
        w = {(u, v): 1 for u, v in A}
    layers = sorted(L.keys())
    new_L = {k: list(L.get(k, [])) for k in layers}
    new_A: list[Edge] = []
    new_w: Weights = {}
    new_t: Flags = {}
    int_nodes = [n for n in V if isinstance(n, int)]
    next_dummy = max(int_nodes) + 1 if int_nodes else 0
    new_V = list(V)
    layer_index = {k: i for i, k in enumerate(layers)}
    # Sorted-layer iteration preserves the old last-match behavior.
    node_to_layer = {node: layer for layer in layers for node in L.get(layer, [])}
    for u, v in A:
        w_uv = w.get((u, v), 1)
        t_uv = t_val.get((u, v), False)
        u_layer = node_to_layer.get(u)
        v_layer = node_to_layer.get(v)
        if u_layer is None or v_layer is None:
            new_A.append((u, v))
            new_w[u, v] = w_uv
            new_t[u, v] = t_uv
            continue
        i_u = layer_index[u_layer]
        i_v = layer_index[v_layer]
        M = len(layers)
        forward_steps = (i_v - i_u) % M
        if forward_steps == 0 or forward_steps == 1:
            new_A.append((u, v))
            new_w[u, v] = w_uv
            new_t[u, v] = t_uv
            continue
        prev = u
        for s in range(1, forward_steps):
            next_idx = (i_u + s) % M
            layer_k = layers[next_idx]
            dummy = next_dummy
            next_dummy += 1
            new_V.append(dummy)
            new_L[layer_k].append(dummy)
            new_A.append((prev, dummy))
            new_w[prev, dummy] = w_uv
            cur_idx = (i_u + s - 1) % M
            wrap_segment = cur_idx == M - 1 and next_idx == 0
            new_t[prev, dummy] = wrap_segment
            prev = dummy
        new_A.append((prev, v))
        new_w[prev, v] = w_uv
        last_from_idx = (i_u + forward_steps - 1) % M
        last_wrap = last_from_idx == M - 1 and i_v == 0
        new_t[prev, v] = last_wrap or (forward_steps == 0 and t_uv)
    return (new_V, new_A, new_L, new_t, new_w)


def insert_dummy_nodes(
    graph: Graph,
    assignment: LayerAssignmentResult,
    *,
    layers: Layers | None = None,
    w: Weights | None = None
) -> SubdividedGraph:
    """明示した空レイヤーも保持する。省略時は階層割当から導出する。"""
    layer_map = assignment.layers if layers is None else layers
    nodes, edges, divided_layers, flags, weights = _insert_dummy_node(
        list(graph.nodes), list(graph.edges), layer_map, assignment.torus_flags, w
    )
    return SubdividedGraph(
        Graph(tuple(nodes), tuple(edges)), divided_layers, flags, weights, graph.nodes
    )
