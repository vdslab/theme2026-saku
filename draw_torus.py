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

    # 各ノードの座標を設定
    for layer_num, nodes in node_order.items():
        for idx, node in enumerate(nodes):
            # x座標：レイヤーの値
            # y座標：各レイヤーの配列の添字（最適化された順序）
            pos[node] = (layer_num, idx)

    # 各ノードがどのレイヤーに属するかを記録
    node_to_layer = {}
    for layer_num, nodes in L.items():
        for node in nodes:
            node_to_layer[node] = layer_num

    # 描画域のサイズを計算
    num_layers = len(L)
    max_layer_size = max(len(nodes) for nodes in L.values()) if L else 0

    # 描画域のサイズは、(レイヤーの数+1) * (最大のレイヤーの要素数+1)
    width = num_layers + 1
    height = max_layer_size + 1

    # レイヤーの最小値と最大値を取得
    min_layer = min(L.keys()) if L else 0
    max_layer = max(L.keys()) if L else 0

    # エッジを通常エッジとトーラス辺に分類
    normal_edges = []
    torus_edges = []

    for u, v in A:
        u_layer = node_to_layer.get(u)
        v_layer = node_to_layer.get(v)
        if u_layer is not None and v_layer is not None:
            # t_valが指定されている場合はそれを使用
            if t_val is not None and t_val.get((u, v), False):
                # トーラス辺
                torus_edges.append((u, v))
            elif t_val is None and u_layer > v_layer:
                # t_valが指定されていない場合は、逆方向エッジをトーラス辺として扱う
                torus_edges.append((u, v))
            else:
                # 通常エッジ
                normal_edges.append((u, v))

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
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=500, node_color="lightblue")
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

        # トーラス経由の x 方向の総距離
        dist_to_right = max_layer + 0.5 - u_pos[0]
        dist_from_left = v_pos[0] - (min_layer - 0.5)
        total_x_dist = dist_to_right + dist_from_left

        # 傾きを一定に保つ（y の変化 / x の変化）
        slope = (v_pos[1] - u_pos[1]) / total_x_dist

        # トーラス境界での高さ（右端と左端で同じ）
        boundary_y = u_pos[1] + slope * dist_to_right

        # u から右端の境界点へ（鏃なし）
        arrow1 = FancyArrowPatch(
            u_pos,
            (max_layer + 0.5, boundary_y),
            arrowstyle="-",
            shrinkA=node_radius * 100,
        )
        ax.add_patch(arrow1)

        # 左端の境界点から v へ（鏃付き）
        arrow2 = FancyArrowPatch(
            (min_layer - 0.5, boundary_y),
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
