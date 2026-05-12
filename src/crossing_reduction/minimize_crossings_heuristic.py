"""
階層グラフの交差削減を行う関数（ヒューリスティック版・トーラス対応）

重心法（Barycenter Method）を用いて、各階層内でのノード順序を最適化する。
トーラス空間（上下左右が繋がった平坦トーラス）に対応したアルゴリズムです。
"""

from typing import Dict, List, Tuple
import copy


def count_crossings(
    layers: Dict[int, List[int]],
    edges: List[Tuple[int, int]],
    t_val: Dict[Tuple[int, int], bool],
) -> int:
    """
    現在のレイヤー配置における全エッジの交差数を計算（トーラス対応版）

    Args:
        layers: レイヤーごとのノードリスト（順序あり） dict[int: list[int]]
        edges: エッジリスト list[tuple(int, int)]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]

    Returns:
        交差数（整数）
    """
    # レイヤーキーを昇順にソート
    layer_keys = sorted(layers.keys())
    num_layers = len(layer_keys)

    # 各ノードの現在の位置（インデックス）を記録
    node_positions = {}
    for k in layer_keys:
        for idx, node in enumerate(layers[k]):
            node_positions[node] = idx

    # ノードがどのレイヤーに属するかを記録
    node_to_layer = {}
    for k in layer_keys:
        for node in layers[k]:
            node_to_layer[node] = k

    # レイヤーのインデックスマップ
    layer_to_index = {k: i for i, k in enumerate(layer_keys)}

    total_crossings = 0

    # 通常の隣接レイヤー間 (i, i+1) の交差をチェック
    for i in range(num_layers - 1):
        current_layer = layer_keys[i]
        next_layer = layer_keys[i + 1]

        # このレイヤー間のエッジを収集（トーラス辺でないもの）
        layer_edges = []
        for u, v in edges:
            if (
                node_to_layer.get(u) == current_layer
                and node_to_layer.get(v) == next_layer
                and not t_val.get((u, v), False)
            ):
                layer_edges.append((u, v))

        # エッジ間の交差をカウント
        for idx1, (u1, v1) in enumerate(layer_edges):
            for idx2 in range(idx1 + 1, len(layer_edges)):
                u2, v2 = layer_edges[idx2]

                # 同一ノードからのエッジは交差しない
                if u1 == u2 or v1 == v2:
                    continue

                pos_u1 = node_positions[u1]
                pos_u2 = node_positions[u2]
                pos_v1 = node_positions[v1]
                pos_v2 = node_positions[v2]

                # 交差判定: (u1, v1) と (u2, v2) が交差する条件
                if (pos_u1 < pos_u2 and pos_v1 > pos_v2) or (
                    pos_u1 > pos_u2 and pos_v1 < pos_v2
                ):
                    total_crossings += 1

    # 【トーラス対応】最下層（L-1）と最上層（0）の間のトーラス辺の交差をチェック
    if num_layers > 1:
        bottom_layer = layer_keys[-1]  # 最下層
        top_layer = layer_keys[0]  # 最上層

        # トーラス辺（最下層から最上層へのエッジ）を収集
        torus_edges = []
        for u, v in edges:
            if (
                node_to_layer.get(u) == bottom_layer
                and node_to_layer.get(v) == top_layer
                and t_val.get((u, v), False)
            ):
                torus_edges.append((u, v))

        # トーラス辺間の交差をカウント
        for idx1, (u1, v1) in enumerate(torus_edges):
            for idx2 in range(idx1 + 1, len(torus_edges)):
                u2, v2 = torus_edges[idx2]

                # 同一ノードからのエッジは交差しない
                if u1 == u2 or v1 == v2:
                    continue

                pos_u1 = node_positions[u1]
                pos_u2 = node_positions[u2]
                pos_v1 = node_positions[v1]
                pos_v2 = node_positions[v2]

                # 交差判定（通常と同じロジック）
                if (pos_u1 < pos_u2 and pos_v1 > pos_v2) or (
                    pos_u1 > pos_u2 and pos_v1 < pos_v2
                ):
                    total_crossings += 1

    return total_crossings


def count_crossings_between_layers(
    fixed_layer: List[int],
    free_layer: List[int],
    edges: List[Tuple[int, int]],
    fixed_positions: Dict[int, int],
    free_positions: Dict[int, int],
    is_torus_pair: bool = False,
) -> int:
    """
    2つのレイヤー間のエッジの交差数を計算（巡回シフト評価用）

    Args:
        fixed_layer: 固定レイヤーのノードリスト
        free_layer: 自由レイヤーのノードリスト
        edges: エッジリスト
        fixed_positions: 固定レイヤーのノード位置
        free_positions: 自由レイヤーのノード位置
        is_torus_pair: トーラス辺のペアか（L-1とL0の間）

    Returns:
        交差数
    """
    # このレイヤー間のエッジを収集
    layer_edges = []
    fixed_set = set(fixed_layer)
    free_set = set(free_layer)

    for u, v in edges:
        if u in fixed_positions and v in free_positions:
            layer_edges.append((u, v))

    crossings = 0
    for idx1, (u1, v1) in enumerate(layer_edges):
        for idx2 in range(idx1 + 1, len(layer_edges)):
            u2, v2 = layer_edges[idx2]

            if u1 == u2 or v1 == v2:
                continue

            pos_u1 = fixed_positions[u1]
            pos_u2 = fixed_positions[u2]
            pos_v1 = free_positions[v1]
            pos_v2 = free_positions[v2]

            if (pos_u1 < pos_u2 and pos_v1 > pos_v2) or (
                pos_u1 > pos_u2 and pos_v1 < pos_v2
            ):
                crossings += 1

    return crossings


def compute_barycenter(
    node: int,
    fixed_layer: List[int],
    edges: List[Tuple[int, int]],
    node_positions: Dict[int, int],
    is_downward: bool,
    is_torus_pair: bool = False,
) -> float:
    """
    指定されたノードの重心（barycenter）を計算（トーラス対応版）

    Args:
        node: 重心を計算するノード
        fixed_layer: 固定レイヤーのノードリスト
        edges: 全エッジリスト
        node_positions: 各ノードの現在の位置 dict[node: position]
        is_downward: 下方向スイープか（Trueなら下方向、Falseなら上方向）
        is_torus_pair: トーラス辺のペアか（L-1とL0の間）

    Returns:
        重心値（float）。隣接ノードがない場合は現在の位置
    """
    # 固定レイヤー内の隣接ノードを探す
    adjacent_positions = []

    for u, v in edges:
        if is_downward:
            # 下方向: nodeが自由レイヤー（v側）、固定レイヤーがu側
            if v == node and u in node_positions:
                adjacent_positions.append(node_positions[u])
        else:
            # 上方向: nodeが自由レイヤー（u側）、固定レイヤーがv側
            if u == node and v in node_positions:
                adjacent_positions.append(node_positions[v])

    # 隣接ノードがない場合は現在の位置を返す
    if not adjacent_positions:
        return node_positions.get(node, 0)

    # 重心を計算（平均値）
    return sum(adjacent_positions) / len(adjacent_positions)


def apply_cyclic_shift(
    sorted_nodes: List[int],
    fixed_layer: List[int],
    edges: List[Tuple[int, int]],
    fixed_positions: Dict[int, int],
    is_torus_pair: bool = False,
) -> List[int]:
    """
    【巡回シフト最適化】
    ソート後のノード配列に対して全巡回シフトパターンを試し、
    固定レイヤーとの交差数が最小になる配置を返す

    Args:
        sorted_nodes: 重心でソート済みのノードリスト
        fixed_layer: 固定レイヤーのノードリスト
        edges: エッジリスト
        fixed_positions: 固定レイヤーのノード位置
        is_torus_pair: トーラス辺のペアか

    Returns:
        最適な巡回シフト後のノードリスト
    """
    if len(sorted_nodes) == 0:
        return sorted_nodes

    best_shift = 0
    best_crossings = float("inf")

    # 全巡回シフトパターンを試す
    for shift in range(len(sorted_nodes)):
        # 巡回シフトを適用
        # shift=0: [A,B,C,D]
        # shift=1: [D,A,B,C] (右に1つシフト = 左に3つシフト)
        # shift=2: [C,D,A,B]
        shifted = (
            sorted_nodes[-shift:] + sorted_nodes[:-shift] if shift > 0 else sorted_nodes
        )

        # このシフト状態での位置マップを作成
        free_positions = {node: idx for idx, node in enumerate(shifted)}

        # 固定レイヤーとの交差数を計算
        crossings = count_crossings_between_layers(
            fixed_layer, shifted, edges, fixed_positions, free_positions, is_torus_pair
        )

        # より良い配置が見つかったら更新
        if crossings < best_crossings:
            best_crossings = crossings
            best_shift = shift

    # 最適なシフトを適用して返す
    if best_shift > 0:
        return sorted_nodes[-best_shift:] + sorted_nodes[:-best_shift]
    else:
        return sorted_nodes


def minimize_crossings_heuristic(V, A, L, t_val, w=None, max_iterations=50):
    """
    階層グラフの交差を最小化するノード順序を計算（重心法・トーラス対応版）

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        L: レイヤー集合 dict[int: list[int]]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]
        w: エッジ重み dict[(int,int): float] (デフォルト: すべて1) ※今回は使用しない
        max_iterations: 最大イテレーション回数（デフォルト: 50）

    Returns:
        (order, L, A, t_val):
            - order: 各階層内のノード順序 dict[int: list[int]]
            - L: ダミー挿入後のレイヤー辞書 dict[int: list[int]]
            - A: ダミー挿入後のエッジリスト list[tuple(int, int)]
            - t_val: ダミー挿入後のトーラスフラグ dict[(int,int): bool]
    """

    # エッジ重みのデフォルト値（今回は使用しないが互換性のため保持）
    if w is None:
        w = {(u, v): 1 for (u, v) in A}

    # 階層のリスト
    layers = sorted(L.keys())

    # ========== ダミーノードの挿入（ILP版と同じロジック） ==========
    new_L = {k: list(L.get(k, [])) for k in layers}
    new_A = []
    new_w = {}
    new_t = {}

    # 次のダミーノードID
    int_nodes = [n for n in V if isinstance(n, int)]
    next_dummy = max(int_nodes) + 1 if int_nodes else 0

    # レイヤーのインデックスマップ
    layer_index = {k: i for i, k in enumerate(layers)}

    for u, v in A:
        w_uv = w.get((u, v), 1) if w is not None else 1
        t_uv = t_val.get((u, v), False)

        # ノードのレイヤーを探す
        u_layer = None
        v_layer = None
        for k in layers:
            if u in L.get(k, []):
                u_layer = k
            if v in L.get(k, []):
                v_layer = k

        if u_layer is None or v_layer is None:
            # レイヤー不明なら元の辺を追加
            new_A.append((u, v))
            new_w[(u, v)] = w_uv
            new_t[(u, v)] = t_uv
            continue

        i_u = layer_index[u_layer]
        i_v = layer_index[v_layer]

        if abs(i_v - i_u) <= 1:
            # 隣接層または同層はそのまま保持
            new_A.append((u, v))
            new_w[(u, v)] = w_uv
            new_t[(u, v)] = t_uv
            continue

        # 長距離辺を分解：階層の増減に基づいて経路を選択
        prev = u
        M = len(layers)

        # モジュラー上の前方ステップ数
        forward_steps = (i_v - i_u) % M
        backward_steps = (i_u - i_v) % M

        # 階層の増減に基づいて経路を選択
        # 階層が減少する辺（i_u > i_v）→ トーラス経由（backward）
        # 階層が増加する辺（i_u < i_v）→ 通常経路（forward）
        # 同一階層（i_u == i_v）→ forward（実際には隣接層判定で除外済み）
        if i_u > i_v:
            # 階層が減少：backward経路を選択（トーラス経由）
            steps = backward_steps
            direction = -1
        else:
            # 階層が増加または同一：forward経路を選択
            steps = forward_steps
            direction = 1

        # 各ステップで中間レイヤーにダミーを挿入
        for s in range(1, steps + 1):
            next_idx = (i_u + direction * s) % M
            layer_k = layers[next_idx]
            dummy = next_dummy
            next_dummy += 1
            new_L[layer_k].append(dummy)
            new_A.append((prev, dummy))
            new_w[(prev, dummy)] = w_uv

            # トーラス境界をまたぐか判定
            cur_idx = (i_u + direction * (s - 1)) % M
            wrap_segment = (cur_idx == M - 1 and next_idx == 0) or (
                cur_idx == 0 and next_idx == M - 1
            )
            new_t[(prev, dummy)] = bool(wrap_segment)
            prev = dummy

        # 最後のセグメント
        new_A.append((prev, v))
        new_w[(prev, v)] = w_uv
        last_from_idx = (i_u + direction * steps) % M if steps > 0 else i_u
        last_wrap = (last_from_idx == M - 1 and i_v % M == 0) or (
            last_from_idx == 0 and i_v % M == M - 1
        )
        new_t[(prev, v)] = bool(last_wrap or (steps == 0 and t_uv))

    # 置換
    L = new_L
    A = new_A
    w = new_w
    t_val = new_t
    layers = sorted(L.keys())

    # ========== 重心法による交差削減（トーラス対応） ==========

    # 初期順序をコピー（現在の順序を保持）
    current_layers = {k: list(L[k]) for k in layers}

    # 初期交差数を計算
    best_crossings = count_crossings(current_layers, A, t_val)
    best_layers = copy.deepcopy(current_layers)

    print(f"初期交差数: {best_crossings}")

    num_layers = len(layers)

    # イテレーション
    for iteration in range(max_iterations):

        # ========== 下方向スイープ (Downward Sweep) - トーラス対応 ==========
        # レイヤー i-1 を固定、レイヤー i を自由レイヤーとする
        # 通常のレイヤー間: i = 1 から num_layers-1 まで
        for i in range(1, num_layers):
            fixed_layer_key = layers[i - 1]
            free_layer_key = layers[i]

            # 現在の位置情報を構築
            node_positions = {}
            for idx, node in enumerate(current_layers[fixed_layer_key]):
                node_positions[node] = idx
            for idx, node in enumerate(current_layers[free_layer_key]):
                node_positions[node] = idx

            # 自由レイヤーの各ノードの重心を計算
            barycenters = []
            for node in current_layers[free_layer_key]:
                bc = compute_barycenter(
                    node,
                    current_layers[fixed_layer_key],
                    A,
                    node_positions,
                    is_downward=True,
                    is_torus_pair=False,
                )
                barycenters.append((bc, node))

            # 重心値の昇順でソート（安定ソート）
            barycenters.sort(key=lambda x: x[0])
            sorted_nodes = [node for _, node in barycenters]

            # 【巡回シフト最適化】固定レイヤーの位置情報
            fixed_positions = {
                node: idx for idx, node in enumerate(current_layers[fixed_layer_key])
            }

            # 全巡回シフトを試して最良の配置を見つける
            optimized_nodes = apply_cyclic_shift(
                sorted_nodes,
                current_layers[fixed_layer_key],
                A,
                fixed_positions,
                is_torus_pair=False,
            )

            # 新しい順序を適用
            current_layers[free_layer_key] = optimized_nodes

        # 【トーラス対応】最下層を固定し、最上層を自由レイヤーとして処理
        if num_layers > 1:
            fixed_layer_key = layers[-1]  # 最下層 (L-1)
            free_layer_key = layers[0]  # 最上層 (L0)

            # 現在の位置情報を構築
            node_positions = {}
            for idx, node in enumerate(current_layers[fixed_layer_key]):
                node_positions[node] = idx
            for idx, node in enumerate(current_layers[free_layer_key]):
                node_positions[node] = idx

            # 自由レイヤーの各ノードの重心を計算
            barycenters = []
            for node in current_layers[free_layer_key]:
                bc = compute_barycenter(
                    node,
                    current_layers[fixed_layer_key],
                    A,
                    node_positions,
                    is_downward=True,
                    is_torus_pair=True,
                )
                barycenters.append((bc, node))

            # 重心値の昇順でソート
            barycenters.sort(key=lambda x: x[0])
            sorted_nodes = [node for _, node in barycenters]

            # 【巡回シフト最適化】
            fixed_positions = {
                node: idx for idx, node in enumerate(current_layers[fixed_layer_key])
            }
            optimized_nodes = apply_cyclic_shift(
                sorted_nodes,
                current_layers[fixed_layer_key],
                A,
                fixed_positions,
                is_torus_pair=True,
            )

            current_layers[free_layer_key] = optimized_nodes

        # ========== 上方向スイープ (Upward Sweep) - トーラス対応 ==========
        # レイヤー i+1 を固定、レイヤー i を自由レイヤーとする
        # 通常のレイヤー間: i = num_layers-2 から 0 まで
        for i in range(num_layers - 2, -1, -1):
            free_layer_key = layers[i]
            fixed_layer_key = layers[i + 1]

            # 現在の位置情報を構築
            node_positions = {}
            for idx, node in enumerate(current_layers[fixed_layer_key]):
                node_positions[node] = idx
            for idx, node in enumerate(current_layers[free_layer_key]):
                node_positions[node] = idx

            # 自由レイヤーの各ノードの重心を計算
            barycenters = []
            for node in current_layers[free_layer_key]:
                bc = compute_barycenter(
                    node,
                    current_layers[fixed_layer_key],
                    A,
                    node_positions,
                    is_downward=False,
                    is_torus_pair=False,
                )
                barycenters.append((bc, node))

            # 重心値の昇順でソート
            barycenters.sort(key=lambda x: x[0])
            sorted_nodes = [node for _, node in barycenters]

            # 【巡回シフト最適化】
            fixed_positions = {
                node: idx for idx, node in enumerate(current_layers[fixed_layer_key])
            }
            optimized_nodes = apply_cyclic_shift(
                sorted_nodes,
                current_layers[fixed_layer_key],
                A,
                fixed_positions,
                is_torus_pair=False,
            )

            current_layers[free_layer_key] = optimized_nodes

        # 【トーラス対応】最上層を固定し、最下層を自由レイヤーとして処理
        if num_layers > 1:
            free_layer_key = layers[-1]  # 最下層 (L-1)
            fixed_layer_key = layers[0]  # 最上層 (L0)

            # 現在の位置情報を構築
            node_positions = {}
            for idx, node in enumerate(current_layers[fixed_layer_key]):
                node_positions[node] = idx
            for idx, node in enumerate(current_layers[free_layer_key]):
                node_positions[node] = idx

            # 自由レイヤーの各ノードの重心を計算
            barycenters = []
            for node in current_layers[free_layer_key]:
                bc = compute_barycenter(
                    node,
                    current_layers[fixed_layer_key],
                    A,
                    node_positions,
                    is_downward=False,
                    is_torus_pair=True,
                )
                barycenters.append((bc, node))

            # 重心値の昇順でソート
            barycenters.sort(key=lambda x: x[0])
            sorted_nodes = [node for _, node in barycenters]

            # 【巡回シフト最適化】
            fixed_positions = {
                node: idx for idx, node in enumerate(current_layers[fixed_layer_key])
            }
            optimized_nodes = apply_cyclic_shift(
                sorted_nodes,
                current_layers[fixed_layer_key],
                A,
                fixed_positions,
                is_torus_pair=True,
            )

            current_layers[free_layer_key] = optimized_nodes

        # イテレーション後の交差数を計算
        current_crossings = count_crossings(current_layers, A, t_val)

        # ベスト状態を更新
        if current_crossings < best_crossings:
            best_crossings = current_crossings
            best_layers = copy.deepcopy(current_layers)
            print(f"イテレーション {iteration + 1}: 交差数 = {best_crossings} (改善)")

        # 交差数が0になったら終了
        if best_crossings == 0:
            print(f"イテレーション {iteration + 1}: 交差数0を達成。終了。")
            break

    # 最終結果
    print(f"\n重心法最適化完了!")
    print(f"最終交差数: {best_crossings}")

    # 各階層のノード順序を出力
    order = {}
    for k in layers:
        order[k] = best_layers[k]
        print(f"階層 {k}: {order[k]}")

    return order, L, A, t_val
