"""
平坦トーラス（Radial Layout）を描画する関数

通常の階層レイアウト + Radial Layoutの組み合わせ:
- 左右のトーラス: 最右レイヤーから最左レイヤーへの逆辺（既存実装と同じ）
- 上下のトーラス: ray（各レイヤーの上下境界）をまたぐエッジ（ψ≠0）
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from collections import defaultdict, deque


def draw_radial_torus(
    V,
    A,
    L,
    order=None,
    psi=None,
    t_val=None,
    save_path=None,
    show=True,
    draw_dummy_nodes=False,
    align_edges=True,
    alignment_iterations=8,
):
    """
    平坦トーラスグラフを描画（階層レイアウト + Radial境界）

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        L: レイヤー集合 dict[int: list[int]]
        order: 各階層内のノード順序 dict[layer: list[nodes]] (オプション)
        psi: 各エッジの巻き数 dict[(u,v): int] (オプション、-1/0/+1)
        t_val: 各エッジがトーラス辺か dict[(int,int): bool] (オプション、左右のトーラス用)
        save_path: 画像の保存先パス (オプション)
        show: 画面表示するかどうか (デフォルト: True)
        draw_dummy_nodes: Vに含まれないノードを黒点で描画するかどうか
        align_edges: 層内順序を保ったまま、エッジが横軸に近づくようy座標を調整するか
        alignment_iterations: align_edges=True のときの反復回数
    """
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

    # 描画域のサイズを計算
    num_layers = len(sorted_layers)
    max_layer_size = max(len(nodes) for nodes in L.values()) if L else 0

    # 描画域の物理的な幅・高さ
    x_min, x_max = -0.5, num_layers - 0.5
    y_min, y_max = -0.5, max_layer_size - 0.5

    # 分割幅（レイヤーごとの幅）
    seg_w = (x_max - x_min) / num_layers if num_layers > 0 else 1.0

    pos = _assign_positions(
        A=A,
        L=L,
        node_order=node_order,
        sorted_layers=sorted_layers,
        layer_index=layer_index,
        x_min=x_min,
        seg_w=seg_w,
        max_layer_size=max_layer_size,
        align_edges=align_edges,
        alignment_iterations=alignment_iterations,
    )

    V_set = set(V)
    dummy_nodes = [node for node in pos if node not in V_set]

    # エッジを分類
    # 1. 左右のトーラス辺（t_val=True）
    # 2. 上下のトーラス辺（psi≠0）
    # 3. 通常辺（それ以外）

    if draw_dummy_nodes:
        # ダミーノード表示時は実エッジをそのまま描画
        left_right_torus = []  # 左右のトーラス
        top_bottom_torus_up = []  # 上側のトーラス（psi > 0）
        top_bottom_torus_down = []  # 下側のトーラス（psi < 0）
        normal_edges = []

        for u, v in A:
            is_lr_torus = bool(t_val.get((u, v), False)) if t_val is not None else False
            winding = psi.get((u, v), 0) if psi is not None else 0

            if is_lr_torus:
                left_right_torus.append((u, v))
            elif winding > 0:
                top_bottom_torus_up.append((u, v))
            elif winding < 0:
                top_bottom_torus_down.append((u, v))
            else:
                normal_edges.append((u, v))
    else:
        # ダミーノードを表示しない場合の処理（既存実装と同様）
        succ = defaultdict(list)
        for u, v in A:
            succ[u].append(v)

        display_edges = {}  # (u,v) -> (combined_t, combined_psi)

        for start in V:
            if start not in succ:
                continue
            for nxt in succ[start]:
                stack = deque()
                combined_t = (
                    bool(t_val.get((start, nxt), False)) if t_val is not None else False
                )
                combined_psi = psi.get((start, nxt), 0) if psi is not None else 0
                stack.append((nxt, combined_t, combined_psi, {(start, nxt)}))

                while stack:
                    cur, cur_t, cur_psi, visited_edges = stack.pop()
                    if cur in V_set:
                        if cur != start:
                            key = (start, cur)
                            if key not in display_edges:
                                display_edges[key] = (cur_t, cur_psi)
                            else:
                                old_t, old_psi = display_edges[key]
                                display_edges[key] = (old_t or cur_t, old_psi + cur_psi)
                        continue

                    for s in succ.get(cur, []):
                        edge_t = (
                            bool(t_val.get((cur, s), False))
                            if t_val is not None
                            else False
                        )
                        edge_psi = psi.get((cur, s), 0) if psi is not None else 0
                        new_t = cur_t or edge_t
                        new_psi = cur_psi + edge_psi
                        edge = (cur, s)
                        if edge in visited_edges or len(visited_edges) > 1000:
                            continue
                        new_visited = set(visited_edges)
                        new_visited.add(edge)
                        stack.append((s, new_t, new_psi, new_visited))

        left_right_torus = []
        top_bottom_torus_up = []
        top_bottom_torus_down = []
        normal_edges = []

        for (u, v), (flag_t, flag_psi) in display_edges.items():
            u_layer = node_to_layer.get(u)
            v_layer = node_to_layer.get(v)
            if u_layer is not None and v_layer is not None:
                u_idx = layer_index.get(u_layer)
                v_idx = layer_index.get(v_layer)
                # レイヤーが逆転している場合は左右のトーラス
                if u_idx is not None and v_idx is not None and v_idx < u_idx:
                    left_right_torus.append((u, v))
                    continue

            if flag_t:
                left_right_torus.append((u, v))
            elif flag_psi > 0:
                top_bottom_torus_up.append((u, v))
            elif flag_psi < 0:
                top_bottom_torus_down.append((u, v))
            else:
                normal_edges.append((u, v))

    # 描画領域サイズ
    width = max(1, num_layers + 1)
    height = max(1, max_layer_size + 1)

    # 描画
    fig, ax = plt.subplots(figsize=(width * 2, height * 2))
    ax.set_xlim(-0.5, num_layers - 0.5)
    ax.set_ylim(-0.5, max_layer_size - 0.5)

    # ノードサイズの半径
    node_radius = 0.15

    # 通常エッジを描画
    for u, v in normal_edges:
        if u not in pos or v not in pos:
            continue
        u_pos = pos[u]
        v_pos = pos[v]
        arrow = FancyArrowPatch(
            u_pos,
            v_pos,
            arrowstyle="->",
            mutation_scale=20,
            shrinkA=node_radius * 100,
            shrinkB=node_radius * 100,
        )
        ax.add_patch(arrow)

    # 左右のトーラス辺を描画（既存実装と同じ）
    for u, v in left_right_torus:
        if u not in pos or v not in pos:
            continue
        u_pos = pos[u]
        v_pos = pos[v]

        dist_to_right = x_max - u_pos[0]
        dist_from_left = v_pos[0] - x_min
        total_x_dist = dist_to_right + dist_from_left
        slope = (v_pos[1] - u_pos[1]) / total_x_dist
        boundary_y = u_pos[1] + slope * dist_to_right

        # uから右端の境界点へ
        arrow1 = FancyArrowPatch(
            u_pos,
            (x_max, boundary_y),
            arrowstyle="-",
            color="red",
            shrinkA=node_radius * 100,
        )
        ax.add_patch(arrow1)

        # 左端の境界点からvへ
        arrow2 = FancyArrowPatch(
            (x_min, boundary_y),
            v_pos,
            arrowstyle="->",
            mutation_scale=20,
            color="red",
            shrinkB=node_radius * 100,
        )
        ax.add_patch(arrow2)

    # 上下のトーラス辺を描画（rayをまたぐ）
    # 上側のトーラス（psi > 0）
    for u, v in top_bottom_torus_up:
        if u not in pos or v not in pos:
            continue
        u_pos = pos[u]
        v_pos = pos[v]

        # 上端を通る経路
        dist_to_top = y_max - u_pos[1]
        dist_from_bottom = v_pos[1] - y_min
        total_y_dist = dist_to_top + dist_from_bottom
        slope = (v_pos[0] - u_pos[0]) / total_y_dist
        boundary_x = u_pos[0] + slope * dist_to_top

        # uから上端の境界点へ
        arrow1 = FancyArrowPatch(
            u_pos,
            (boundary_x, y_max),
            arrowstyle="-",
            color="blue",
            shrinkA=node_radius * 100,
        )
        ax.add_patch(arrow1)

        # 下端の境界点からvへ
        arrow2 = FancyArrowPatch(
            (boundary_x, y_min),
            v_pos,
            arrowstyle="->",
            mutation_scale=20,
            color="blue",
            shrinkB=node_radius * 100,
        )
        ax.add_patch(arrow2)

    # 下側のトーラス（psi < 0）
    for u, v in top_bottom_torus_down:
        if u not in pos or v not in pos:
            continue
        u_pos = pos[u]
        v_pos = pos[v]

        # 下端を通る経路
        dist_to_bottom = u_pos[1] - y_min
        dist_from_top = y_max - v_pos[1]
        total_y_dist = dist_to_bottom + dist_from_top
        slope = (v_pos[0] - u_pos[0]) / total_y_dist
        boundary_x = u_pos[0] + slope * dist_to_bottom

        # uから下端の境界点へ
        arrow1 = FancyArrowPatch(
            u_pos,
            (boundary_x, y_min),
            arrowstyle="-",
            color="green",
            shrinkA=node_radius * 100,
        )
        ax.add_patch(arrow1)

        # 上端の境界点からvへ
        arrow2 = FancyArrowPatch(
            (boundary_x, y_max),
            v_pos,
            arrowstyle="->",
            mutation_scale=20,
            color="green",
            shrinkB=node_radius * 100,
        )
        ax.add_patch(arrow2)

    # ノードを描画
    visible_nodes = [node for node in V if node in pos]
    if visible_nodes:
        xs = [pos[node][0] for node in visible_nodes]
        ys = [pos[node][1] for node in visible_nodes]
        ax.scatter(xs, ys, s=400, c="lightblue", edgecolors="black", zorder=3)
        for node in visible_nodes:
            ax.text(
                pos[node][0],
                pos[node][1],
                str(node),
                ha="center",
                va="center",
                fontsize=10,
                zorder=4,
            )

    if draw_dummy_nodes and dummy_nodes:
        xs = [pos[node][0] for node in dummy_nodes]
        ys = [pos[node][1] for node in dummy_nodes]
        ax.scatter(xs, ys, s=120, c="black", marker="o", zorder=3)

    # y軸を反転（上から下に描画）
    ax.invert_yaxis()

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200)
    if show:
        plt.show()
    plt.close(fig)


def _assign_positions(
    A,
    L,
    node_order,
    sorted_layers,
    layer_index,
    x_min,
    seg_w,
    max_layer_size,
    align_edges,
    alignment_iterations,
):
    center_y = (max_layer_size - 1) / 2 if max_layer_size > 0 else 0.0
    y_by_node = {}

    for layer_num in sorted_layers:
        nodes = node_order.get(layer_num, L.get(layer_num, []))
        centered_y = _centered_positions(len(nodes), center_y)
        for node, y in zip(nodes, centered_y):
            y_by_node[node] = y

    if align_edges:
        adjacency = defaultdict(list)
        for u, v in A:
            if u in y_by_node and v in y_by_node:
                adjacency[u].append(v)
                adjacency[v].append(u)

        for _ in range(max(0, alignment_iterations)):
            next_y = dict(y_by_node)
            for layer_num in sorted_layers:
                nodes = node_order.get(layer_num, L.get(layer_num, []))
                if not nodes:
                    continue

                targets = []
                for node in nodes:
                    neighbors = adjacency.get(node, [])
                    if neighbors:
                        neighbor_y = sum(y_by_node[n] for n in neighbors) / len(neighbors)
                        targets.append(0.7 * neighbor_y + 0.3 * y_by_node[node])
                    else:
                        targets.append(y_by_node[node])

                projected = _project_ordered_centered(
                    targets, center_y, max_span=max(0, max_layer_size - 1)
                )
                for node, y in zip(nodes, projected):
                    next_y[node] = y
            y_by_node = next_y

    pos = {}
    for layer_num in sorted_layers:
        x = x_min + seg_w * (layer_index[layer_num] + 0.5)
        nodes = node_order.get(layer_num, L.get(layer_num, []))
        for node in nodes:
            pos[node] = (x, y_by_node[node])

    return pos


def _centered_positions(count, center_y):
    if count == 0:
        return []
    start = center_y - (count - 1) / 2
    return [start + idx for idx in range(count)]


def _project_ordered_centered(targets, center_y, min_gap=1.0, max_span=None):
    if not targets:
        return []

    shifted_targets = [target - idx * min_gap for idx, target in enumerate(targets)]
    fitted = _isotonic_non_decreasing(shifted_targets)
    positions = [value + idx * min_gap for idx, value in enumerate(fitted)]

    if max_span is not None and positions[-1] - positions[0] > max_span:
        return _centered_positions(len(targets), center_y)

    mean_y = sum(positions) / len(positions)
    shift = center_y - mean_y
    return [position + shift for position in positions]


def _isotonic_non_decreasing(values):
    blocks = []
    for idx, value in enumerate(values):
        blocks.append({"sum": value, "weight": 1, "start": idx, "end": idx})
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            if left["sum"] / left["weight"] <= right["sum"] / right["weight"]:
                break
            merged = {
                "sum": left["sum"] + right["sum"],
                "weight": left["weight"] + right["weight"],
                "start": left["start"],
                "end": right["end"],
            }
            blocks[-2:] = [merged]

    fitted = [0.0] * len(values)
    for block in blocks:
        value = block["sum"] / block["weight"]
        for idx in range(block["start"], block["end"] + 1):
            fitted[idx] = value
    return fitted
