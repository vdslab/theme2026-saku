"""
階層グラフの交差削減を行う関数

サンキーダイアグラムの交差削減手法を適用し、各階層内でのノード順序を最適化する。
"""

import gurobipy as gp
from gurobipy import GRB
from lib.create_gurobi_env import create_gurobi_env


def minimize_crossings_ilp(V, A, L, t_val, w=None):
    """
    階層グラフの交差を最小化するノード順序を計算

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        L: レイヤー集合 dict[int: list[int]]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]
        w: エッジ重み dict[(int,int): float] (デフォルト: すべて1)

    Returns:
        (order, L, A, t_val):
            - order: 各階層内のノード順序 dict[int: list[int]]
            - L: ダミー挿入後のレイヤー辞書 dict[int: list[int]]
            - A: ダミー挿入後のエッジリスト list[tuple(int, int)]
            - t_val: ダミー挿入後のトーラスフラグ dict[(int,int): bool]
    """

    # エッジ重みのデフォルト値
    if w is None:
        w = {(u, v): 1 for (u, v) in A}

    # 階層のリスト
    layers = sorted(L.keys())

    # ダミーノードの挿入
    # new_L: レイヤーごとのノードリストのコピー
    new_L = {k: list(L.get(k, [])) for k in layers}
    new_A = []
    new_w = {}
    new_t = {}

    # 次のダミーノードID（既存が整数ならその次の整数を使う）
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
            # 隣接層または同層はそのまま保持（元向き）
            new_A.append((u, v))
            new_w[(u, v)] = w_uv
            new_t[(u, v)] = t_uv
            continue

        # 長距離辺を分解：階層の増減に基づいて経路を選択
        prev = u
        M = len(layers)

        # モジュラー上の前方ステップ数（u -> v）
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

            # このセグメントがトーラス境界をまたぐか判定
            # 前層インデックスと次層インデックスの差で判定
            cur_idx = (i_u + direction * (s - 1)) % M
            wrap_segment = (cur_idx == M - 1 and next_idx == 0) or (
                cur_idx == 0 and next_idx == M - 1
            )
            # トーラス境界をまたぐセグメントのみ t=True
            new_t[(prev, dummy)] = bool(wrap_segment)
            prev = dummy

        # 最後のセグメント prev -> v
        new_A.append((prev, v))
        new_w[(prev, v)] = w_uv
        # 最後のセグメントがトーラス境界かどうかも判定
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

    env = create_gurobi_env()

    with gp.Model(name="Crossing_Minimization", env=env) as m:

        # ========== 変数定義 ==========

        # x[k, u1, u2]: 階層k内でノードu1がu2の「上」にあるかどうか
        x = {}
        for k in layers:
            nodes = L[k]
            for u1 in nodes:
                for u2 in nodes:
                    if u1 != u2:
                        x[k, u1, u2] = m.addVar(
                            vtype=GRB.BINARY, name=f"x_{k}_{u1}_{u2}"
                        )

        # c[e1, e2]: エッジe1とe2が交差するかどうか
        c = {}
        for idx, k in enumerate(layers[:-1]):  # 最後の層を除く
            next_k = layers[idx + 1]
            edges_k = [(u, v) for (u, v) in A if u in L[k] and v in L.get(next_k, [])]
            for e1 in edges_k:
                for e2 in edges_k:
                    if e1 != e2:
                        c[e1, e2] = m.addVar(vtype=GRB.BINARY, name=f"c_{e1}_{e2}")

        # ========== 制約 ==========

        # 1. 相対位置の一意性: u1とu2のどちらかが上
        for k in layers:
            nodes = L[k]
            for u1 in nodes:
                for u2 in nodes:
                    if u1 < u2:  # 重複を避けるため u1 < u2 のみ
                        m.addConstr(
                            x[k, u1, u2] + x[k, u2, u1] == 1,
                            name=f"unique_{k}_{u1}_{u2}",
                        )

        # 2. 推移性: u3が上、u2が上 → u3がu1の上
        for k in layers:
            nodes = L[k]
            for u1 in nodes:
                for u2 in nodes:
                    for u3 in nodes:
                        if u1 != u2 and u2 != u3 and u1 != u3:
                            m.addConstr(
                                x[k, u3, u1] >= x[k, u3, u2] + x[k, u2, u1] - 1,
                                name=f"trans_{k}_{u1}_{u2}_{u3}",
                            )

        # 3. 交差の定義（通常辺のみ）
        for idx, k in enumerate(layers[:-1]):
            next_k = layers[idx + 1]
            edges_k = [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(next_k, []) and not t_val.get((u, v), False)
            ]

            for e1 in edges_k:
                for e2 in edges_k:
                    if e1 != e2:
                        u1, v1 = e1
                        u2, v2 = e2

                        # u1 != u2 かつ v1 != v2 の場合のみ交差判定
                        if (
                            u1 != u2
                            and v1 != v2
                            and v1 in L.get(next_k, [])
                            and v2 in L.get(next_k, [])
                        ):
                            # 交差条件1: u1が上、v2が上
                            m.addConstr(
                                c[e1, e2] + x[k, u2, u1] + x[next_k, v1, v2] >= 1,
                                name=f"cross1_{e1}_{e2}",
                            )

                            # 交差条件2: u2が上、v1が上
                            m.addConstr(
                                c[e1, e2] + x[k, u1, u2] + x[next_k, v2, v1] >= 1,
                                name=f"cross2_{e1}_{e2}",
                            )

        # 4. 対称性制約（パフォーマンス向上）
        for idx, k in enumerate(layers[:-1]):
            next_k = layers[idx + 1]
            edges_k = [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(next_k, []) and not t_val.get((u, v), False)
            ]

            for e1 in edges_k:
                for e2 in edges_k:
                    if e1 < e2:  # 重複を避ける
                        m.addConstr(c[e1, e2] == c[e2, e1], name=f"sym_{e1}_{e2}")

        # ========== 目的関数 ==========

        # 交差領域の合計を最小化
        terms = []
        for idx, k in enumerate(layers[:-1]):
            next_k = layers[idx + 1]
            edges_k = [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(next_k, []) and not t_val.get((u, v), False)
            ]
            for e1 in edges_k:
                for e2 in edges_k:
                    if e1 != e2:
                        terms.append(w.get(e1, 1) * w.get(e2, 1) * c[e1, e2])

        obj = gp.quicksum(terms)

        m.setObjective(obj, GRB.MINIMIZE)

        # ========== 最適化実行 ==========

        m.optimize()

        # ========== 結果の取得 ==========

        order = {}

        if m.status == GRB.OPTIMAL:
            print(f"\n交差削減最適化成功!")
            print(f"交差数: {m.objVal:.2f}")

            # 各階層のノード順序を復元
            for k in layers:
                nodes = L[k]
                # ノードのスコアを計算（上にあるノードの数）
                scores = {}
                for u in nodes:
                    score = sum(x[k, u, v].X for v in nodes if v != u)
                    scores[u] = score

                # スコアの降順でソート（スコアが高い = より上）
                ordered_nodes = sorted(nodes, key=lambda u: scores[u], reverse=True)
                order[k] = ordered_nodes

                print(f"階層 {k}: {ordered_nodes}")

        else:
            print(f"交差削減最適化失敗: ステータス = {m.status}")
            # フォールバック: 元の順序を返す
            order = {k: list(nodes) for k, nodes in L.items()}

        return order, L, A, t_val
