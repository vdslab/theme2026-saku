"""
平坦トーラス上の階層グラフに対して、長距離エッジを分割するダミーノードを挿入する共通処理
"""


def insert_dummy_node(V, A, L, t_val=None, w=None):
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

    # t_val と w のデフォルト値処理
    if t_val is None:
        t_val = {}
    if w is None:
        w = {(u, v): 1 for (u, v) in A}

    # 階層のリスト
    layers = sorted(L.keys())

    # 新しいデータ構造の初期化
    new_L = {k: list(L.get(k, [])) for k in layers}
    new_A = []
    new_w = {}
    new_t = {}

    # 次のダミーノードID（既存が整数ならその次の整数を使う）
    int_nodes = [n for n in V if isinstance(n, int)]
    next_dummy = max(int_nodes) + 1 if int_nodes else 0

    # 新しいノード集合（ダミーノードが追加される）
    new_V = list(V)

    # レイヤーのインデックスマップ
    layer_index = {k: i for i, k in enumerate(layers)}

    # 各エッジを処理
    for u, v in A:
        w_uv = w.get((u, v), 1)
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

        # 必ず左から右へ進むステップ数を計算（モジュラー演算）
        M = len(layers)
        forward_steps = (i_v - i_u) % M

        # forward_steps == 0（同一層）または forward_steps == 1（隣接層）
        # の場合はダミーを挿入せずそのまま維持
        if forward_steps == 0 or forward_steps == 1:
            new_A.append((u, v))
            new_w[(u, v)] = w_uv
            new_t[(u, v)] = t_uv
            continue

        # 長距離辺を分割（必ず右方向へのループを強制）
        # forward_steps - 1 個のダミーノードを各中間レイヤーに順次挿入
        prev = u

        for s in range(1, forward_steps):
            # 次の階層インデックス（右方向に進む）
            next_idx = (i_u + s) % M
            layer_k = layers[next_idx]

            # ダミーノードを作成
            dummy = next_dummy
            next_dummy += 1
            new_V.append(dummy)
            new_L[layer_k].append(dummy)

            # prev -> dummy のエッジを追加
            new_A.append((prev, dummy))
            new_w[(prev, dummy)] = w_uv

            # このセグメントがトーラス境界をまたぐか判定
            # インデックスが len(layers) - 1 から 0 にジャンプする瞬間
            cur_idx = (i_u + s - 1) % M
            wrap_segment = cur_idx == M - 1 and next_idx == 0
            new_t[(prev, dummy)] = wrap_segment

            prev = dummy

        # 最後のセグメント prev -> v
        new_A.append((prev, v))
        new_w[(prev, v)] = w_uv

        # 最後のセグメントがトーラス境界かどうかも判定
        last_from_idx = (i_u + forward_steps - 1) % M
        last_wrap = last_from_idx == M - 1 and i_v == 0
        new_t[(prev, v)] = last_wrap or (forward_steps == 0 and t_uv)

    return new_V, new_A, new_L, new_t, new_w
