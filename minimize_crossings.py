"""
階層グラフの交差削減を行う関数

サンキーダイアグラムの交差削減手法を適用し、各階層内でのノード順序を最適化する。
"""

import gurobipy as gp
from gurobipy import GRB
from create_gurobi_env import create_gurobi_env


def minimize_crossings(V, A, L, t_val, w=None):
    """
    階層グラフの交差を最小化するノード順序を計算

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        L: レイヤー集合 dict[int: list[int]]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]
        w: エッジ重み dict[(int,int): float] (デフォルト: すべて1)

    Returns:
        order: 各階層内のノード順序 dict[int: list[int]]
    """

    # エッジ重みのデフォルト値
    if w is None:
        w = {(u, v): 1 for (u, v) in A}

    # 階層のリスト
    layers = sorted(L.keys())

    # ダミーノードの挿入

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
        for k in layers[:-1]:  # 最後の層を除く
            edges_k = [(u, v) for (u, v) in A if u in L[k] and v in L.get(k + 1, [])]
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
        for k in layers[:-1]:
            edges_k = [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(k + 1, []) and not t_val.get((u, v), False)
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
                            and v1 in L.get(k + 1, [])
                            and v2 in L.get(k + 1, [])
                        ):
                            # 交差条件1: u1が上、v2が上
                            m.addConstr(
                                c[e1, e2] + x[k, u2, u1] + x[k + 1, v1, v2] >= 1,
                                name=f"cross1_{e1}_{e2}",
                            )

                            # 交差条件2: u2が上、v1が上
                            m.addConstr(
                                c[e1, e2] + x[k, u1, u2] + x[k + 1, v2, v1] >= 1,
                                name=f"cross2_{e1}_{e2}",
                            )

        # 4. 対称性制約（パフォーマンス向上）
        for k in layers[:-1]:
            edges_k = [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(k + 1, []) and not t_val.get((u, v), False)
            ]

            for e1 in edges_k:
                for e2 in edges_k:
                    if e1 < e2:  # 重複を避ける
                        m.addConstr(c[e1, e2] == c[e2, e1], name=f"sym_{e1}_{e2}")

        # ========== 目的関数 ==========

        # 交差領域の合計を最小化
        obj = gp.quicksum(
            w.get(e1, 1) * w.get(e2, 1) * c[e1, e2]
            for k in layers[:-1]
            for e1 in [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(k + 1, []) and not t_val.get((u, v), False)
            ]
            for e2 in [
                (u, v)
                for (u, v) in A
                if u in L[k] and v in L.get(k + 1, []) and not t_val.get((u, v), False)
            ]
            if e1 != e2
        )

        m.setObjective(obj, GRB.MINIMIZE)

        # ========== 最適化実行 ==========

        m.optimize()

        # ========== 結果の取得 ==========

        order = {}

        if m.status == GRB.OPTIMAL:
            print(f"\n交差削減最適化成功!")
            print(f"交差数（重み付き）: {m.objVal:.2f}")

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

        return order
