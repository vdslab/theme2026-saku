"""
トーラスを描画する関数

Args:
    V: ノード集合 int[]
    A: エッジ集合 [int, int][]
    L: レイヤー集合 dict(layer: node[])
"""

import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from collections import defaultdict, deque


def draw_torus(V, A, L, t_val=None, order=None):
    """
    トーラスグラフを描画

    Args:
        V: ノード集合
        A: エッジ集合
        L: レイヤー集合
        t_val: 各エッジがトーラス辺かどうか（オプション）
        order: 各階層内のノード順序（オプション）dict[layer: list[nodes]]
    """
    # ノードの位置を決定
    pos = {}

    # orderが指定されている場合はそれを使用、なければLの順序を使用
    if order is not None:
        node_order = order
    else:
        node_order = L

    # レイヤーキーをソートして連番インデックスにマップ
    sorted_layers = sorted(L.keys())
    layer_index = {layer: i for i, layer in enumerate(sorted_layers)}

    # 各ノードがどのレイヤーに属するかを記録
    node_to_layer = {}
    for layer_num, nodes in L.items():
        for node in nodes:
            node_to_layer[node] = layer_num

    # 描画域のサイズを計算（レイヤー数と最大レイヤーサイズで分割）
    num_layers = len(sorted_layers)
    max_layer_size = max(len(nodes) for nodes in L.values()) if L else 0

    # 描画域の物理的な幅・高さ（現在の実装と同じマージン指定を利用）
    x_min, x_max = -0.5, num_layers - 0.5
    y_min, y_max = -0.5, max_layer_size - 0.5

    # 分割幅（レイヤーごとの幅、ノードごとの高さ）
    seg_w = (x_max - x_min) / num_layers if num_layers > 0 else 1.0
    seg_h = (y_max - y_min) / max_layer_size if max_layer_size > 0 else 1.0

    # 各ノードの座標を設定（x: レイヤーの連番位置の中央、y: レイヤー内の均等配置）
    for layer_num in sorted_layers:
        i = layer_index[layer_num]
        nodes = node_order.get(layer_num, L.get(layer_num, []))
        for idx, node in enumerate(nodes):
            # x はそのレイヤーの中央位置
            x = x_min + seg_w * (i + 0.5)
            # y はレイヤー内で均等に並べる（上から下に表示されるため idx のまま）
            y = y_min + seg_h * (idx + 0.5)
            pos[node] = (x, y)

    # ダミーノードは描画しない。ダミー経由のチェインを原点間の表示エッジに折り畳む。
    V_set = set(V)
    succ = defaultdict(list)
    for u, v in A:
        succ[u].append(v)

    display_edges = {}  # (u,v) -> combined_t

    # 探索して start(元ノード) -> end(元ノード) のパスを見つける
    for start in V:
        if start not in succ:
            continue
        for nxt in succ[start]:
            # BFS/DFS along successors until reach an original node (in V_set)
            stack = deque()
            combined_t = (
                bool(t_val.get((start, nxt), False))
                if t_val is not None
                else (False if start <= nxt else True)
            )
            stack.append((nxt, combined_t, {(start, nxt)}))
            while stack:
                cur, cur_t, visited_edges = stack.pop()
                if cur in V_set:
                    if cur != start:
                        key = (start, cur)
                        display_edges[key] = display_edges.get(key, False) or cur_t
                    continue

                # cur is dummy; follow its successors
                for s in succ.get(cur, []):
                    edge_t = (
                        bool(t_val.get((cur, s), False)) if t_val is not None else False
                    )
                    new_t = cur_t or edge_t
                    edge = (cur, s)
                    if edge in visited_edges:
                        continue
                    if len(visited_edges) > 1000:
                        # safety guard
                        continue
                    new_visited = set(visited_edges)
                    new_visited.add(edge)
                    stack.append((s, new_t, new_visited))

    normal_edges = []
    torus_edges = []
    for (u, v), flag in display_edges.items():
        # レイヤー順序を確認し、end が start より前の層にある場合はトーラス経由とみなす
        u_layer = node_to_layer.get(u)
        v_layer = node_to_layer.get(v)
        if u_layer is not None and v_layer is not None:
            u_idx = layer_index.get(u_layer)
            v_idx = layer_index.get(v_layer)
            if u_idx is not None and v_idx is not None and v_idx < u_idx:
                torus_edges.append((u, v))
                continue

        if flag:
            torus_edges.append((u, v))
        else:
            normal_edges.append((u, v))

    # 描画領域サイズ（表示の見やすさのため最低1を確保）
    width = max(1, num_layers + 1)
    height = max(1, max_layer_size + 1)

    # 描画
    fig, ax = plt.subplots(figsize=(width * 2, height * 2))

    # 左端のノードは描画域の左端から0.5だけ離して描画
    # 右端のノードは描画域の右端から0.5だけ離して描画
    ax.set_xlim(-0.5, num_layers - 0.5)
    ax.set_ylim(-0.5, max_layer_size - 0.5)

    # グラフを作成（通常エッジのみ）
    G = nx.DiGraph()
    G.add_nodes_from(V)
    G.add_edges_from(normal_edges)

    # ノードサイズの半径（座標単位）
    # node_size=500はポイント単位なので、座標単位に変換
    # 大体の目安として、node_size=500の場合、半径約0.15程度
    node_radius = 0.15

    # ノードと通常エッジを描画
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=400, node_color="lightblue")
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=10)

    # 通常エッジを描画（ノードとの重なりを避けるため、FancyArrowPatchを使用）
    for u, v in normal_edges:
        u_pos = pos[u]
        v_pos = pos[v]
        arrow = FancyArrowPatch(
            u_pos,
            v_pos,
            arrowstyle="->",
            mutation_scale=20,
            shrinkA=node_radius * 100,  # ポイント単位で指定
            shrinkB=node_radius * 100,
        )
        ax.add_patch(arrow)

    # トーラス辺をトーラス接続で描画（視認性向上のため赤色）
    for u, v in torus_edges:
        u_pos = pos[u]
        v_pos = pos[v]

        # トーラス経由の x 方向の総距離（描画領域の左右マージンを使用）
        dist_to_right = x_max - u_pos[0]
        dist_from_left = v_pos[0] - x_min
        total_x_dist = dist_to_right + dist_from_left

        # 傾きを一定に保つ（y の変化 / x の変化）
        slope = (v_pos[1] - u_pos[1]) / total_x_dist

        # トーラス境界での高さ（右端と左端で同じ）
        boundary_y = u_pos[1] + slope * dist_to_right

        # u から右端の境界点へ（鏃なし）
        arrow1 = FancyArrowPatch(
            u_pos,
            (x_max, boundary_y),
            arrowstyle="-",
            shrinkA=node_radius * 100,
        )
        ax.add_patch(arrow1)

        # 左端の境界点から v へ（鏃付き）
        arrow2 = FancyArrowPatch(
            (x_min, boundary_y),
            v_pos,
            arrowstyle="->",
            mutation_scale=20,
            shrinkB=node_radius * 100,
        )
        ax.add_patch(arrow2)

    # y軸を反転（上から下に描画）
    ax.invert_yaxis()

    plt.tight_layout()
    plt.show()
