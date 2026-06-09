"""
階層グラフの交差削減を行う関数

サンキーダイアグラムの交差削減手法を適用し、各階層内でのノード順序を最適化する。
"""

import itertools
import gurobipy as gp
from gurobipy import GRB
from lib.create_gurobi_env import create_gurobi_env
from lib.insert_dummy_node import insert_dummy_node


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

    # ========== ダミーノードの挿入（共通関数を呼び出し） ==========
    V, A, L, t_val, w = insert_dummy_node(V, A, L, t_val, w)
    layers = sorted(L.keys())

    # ========== Gurobiモデルの構築（新しい平坦トーラス用定式化） ==========
    env = create_gurobi_env()

    with gp.Model(name="Crossing_Minimization_Torus", env=env) as m:

        # ========== 変数定義 ==========

        # x[k, u, v]: 階層k内でノードuがvより局所的に「上」にあるか
        # ※対称性を利用し、常に u < v の場合のみ変数を生成して探索空間を半減
        x = {}
        for k in layers:
            nodes = L[k]
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    u, v = nodes[i], nodes[j]
                    if u > v:
                        u, v = v, u  # 必ず u < v の順にする

                    if (k, u, v) not in x:
                        x[k, u, v] = m.addVar(vtype=GRB.BINARY, name=f"x_{k}_{u}_{v}")

        # x[k, u, v] を安全に取得するためのヘルパー関数（逆順の場合は 1 - x で返す）
        def get_x(k, u, v):
            if u < v:
                return x[k, u, v]
            else:
                return 1 - x[k, v, u]

        # alpha[e]: エッジeがY軸の境界をまたぐ回数（巻き付き数）
        # 下限-1、上限1の整数変数
        alpha = {}
        for e in A:
            alpha[e] = m.addVar(
                vtype=GRB.INTEGER, lb=-1, ub=1, name=f"alpha_{e[0]}_{e[1]}"
            )

        # alpha_abs[e]: alpha[e]の絶対値（連続変数、0以上）
        alpha_abs = {}
        for e in A:
            alpha_abs[e] = m.addVar(
                vtype=GRB.CONTINUOUS, lb=0.0, name=f"alpha_abs_{e[0]}_{e[1]}"
            )

        # c[e1, e2]: エッジe1とe2の交差数
        # 多重交差が起きるため連続変数（0以上）とする
        c = {}
        # 環状構造: 最後の階層の次は最初の階層
        num_layers = len(layers)
        for idx in range(num_layers):
            k = layers[idx]
            next_k = layers[(idx + 1) % num_layers]  # 環状にする

            # k層から next_k層へのエッジを取得
            edges_k = [(u, v) for (u, v) in A if u in L[k] and v in L.get(next_k, [])]

            # 独立した（端点を共有しない）エッジペアについて交差変数を作成
            for i, e1 in enumerate(edges_k):
                for j, e2 in enumerate(edges_k):
                    if i < j:  # 重複を避ける（e1 < e2）
                        u1, v1 = e1
                        u2, v2 = e2
                        # 端点を共有しないエッジペアのみ
                        if u1 != u2 and v1 != v2:
                            c[e1, e2] = m.addVar(
                                vtype=GRB.CONTINUOUS, lb=0.0, name=f"c_{e1}_{e2}"
                            )

        # ========== 制約条件の定義 ==========

        # 1. 相対位置の一意性 (Consistency):
        #    -> ヘルパー関数 get_x により構造的に保証されたため、この制約ブロックは不要！

        # 2. 推移律 (Transitivity):
        #    u < v < w_node の組み合わせのみループすることで、制約数を約1/6に削減
        for k in layers:
            # ノードをID順にソートして、確実に u < v < w_node の順で取り出す
            sorted_nodes = sorted(L[k])
            for u, v, w_node in itertools.combinations(sorted_nodes, 3):
                # 3サイクルを禁止する制約（0 <= x_uv + x_vw - x_uw <= 1）
                m.addConstr(
                    x[k, u, v] + x[k, v, w_node] - x[k, u, w_node] >= 0,
                    name=f"trans1_{k}_{u}_{v}_{w_node}",
                )
                m.addConstr(
                    x[k, u, v] + x[k, v, w_node] - x[k, u, w_node] <= 1,
                    name=f"trans2_{k}_{u}_{v}_{w_node}",
                )

        # 3. 巻き付き数の絶対値 (Absolute Winding Number):
        #    alpha_abs[e] >= alpha[e] かつ alpha_abs[e] >= -alpha[e]
        for e in A:
            m.addConstr(alpha_abs[e] >= alpha[e], name=f"abs_pos_{e[0]}_{e[1]}")
            m.addConstr(alpha_abs[e] >= -alpha[e], name=f"abs_neg_{e[0]}_{e[1]}")

        # 4. 交差の定義 (Crossing Calculation):
        #    注意: 旧実装の not t_val.get(e) という除外条件は削除
        #    （横方向の境界をまたぐ辺同士も交差計算の対象）
        for idx in range(num_layers):
            k = layers[idx]
            next_k = layers[(idx + 1) % num_layers]  # 環状構造

            edges_k = [(u, v) for (u, v) in A if u in L[k] and v in L.get(next_k, [])]

            # 独立した（端点を共有しない）エッジペア (e1, e2) について
            for i, e1 in enumerate(edges_k):
                for j, e2 in enumerate(edges_k):
                    if i < j:  # e1 < e2
                        u1, v1 = e1
                        u2, v2 = e2

                        # 端点を共有しないエッジペアのみ交差判定
                        if u1 != u2 and v1 != v2:
                            # 交差数の制約（2つの不等式）:
                            # c[e1, e2] >= (alpha[e1] - alpha[e2]) - get_x(next_k, v1, v2) + get_x(k, u1, u2)
                            m.addConstr(
                                c[e1, e2]
                                >= (alpha[e1] - alpha[e2])
                                - get_x(next_k, v1, v2)
                                + get_x(k, u1, u2),
                                name=f"crossing1_{e1}_{e2}",
                            )
                            # c[e1, e2] >= -(alpha[e1] - alpha[e2]) + get_x(next_k, v1, v2) - get_x(k, u1, u2)
                            m.addConstr(
                                c[e1, e2]
                                >= -(alpha[e1] - alpha[e2])
                                + get_x(next_k, v1, v2)
                                - get_x(k, u1, u2),
                                name=f"crossing2_{e1}_{e2}",
                            )

        # ========== 目的関数の設定 ==========
        # 最小化: Sum(w[e1] * w[e2] * c[e1, e2]) + 0.001 * Sum(alpha_abs[e])
        #
        # 第1項: 重み付き交差数の総和
        # 第2項: 無駄な境界またぎを抑制するペナルティ（視覚的スパゲッティ化防止）

        crossing_terms = []
        for idx in range(num_layers):
            k = layers[idx]
            next_k = layers[(idx + 1) % num_layers]
            edges_k = [(u, v) for (u, v) in A if u in L[k] and v in L.get(next_k, [])]

            for i, e1 in enumerate(edges_k):
                for j, e2 in enumerate(edges_k):
                    if i < j:
                        u1, v1 = e1
                        u2, v2 = e2
                        if u1 != u2 and v1 != v2:
                            w1 = w.get(e1, 1)
                            w2 = w.get(e2, 1)
                            crossing_terms.append(w1 * w2 * c[e1, e2])

        # 巻き付き数ペナルティ項
        winding_penalty_terms = [0.001 * alpha_abs[e] for e in A]

        # 目的関数を設定
        obj = gp.quicksum(crossing_terms) + gp.quicksum(winding_penalty_terms)
        m.setObjective(obj, GRB.MINIMIZE)

        # ========== 最適化実行 ==========

        m.optimize()

        # ========== 結果の取得 ==========

        order = {}

        if m.status == GRB.OPTIMAL or m.status == GRB.TIME_LIMIT:
            if m.status == GRB.OPTIMAL:
                print(f"\n=== 平坦トーラス交差削減最適化成功 ===")
            else:
                print(f"\n=== タイムリミット到達（最良解を使用） ===")

            total_crossings = round(sum(c[e1, e2].X for (e1, e2) in c.keys()))
            print(f"交差数: {total_crossings} 回")

            # 各階層のノード順序を復元
            for k in layers:
                nodes = L[k]
                # 各ノードのスコアを計算
                # スコア = そのノードより下にあるノードの数（get_x を使って計算）
                scores = {}
                for u in nodes:
                    score = 0
                    for v in nodes:
                        if v != u:
                            # get_x の返り値が式（LinExpr）または変数（Var）
                            x_val = get_x(k, u, v)
                            if isinstance(x_val, (int, float)):
                                score += x_val
                            elif hasattr(x_val, "getValue"):
                                # 線形式の場合
                                score += x_val.getValue()
                            else:
                                # 変数の場合
                                score += x_val.X
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
