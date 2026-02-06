"""
トーラスを含む階層グラフの階層割当を最適化する関数

トーラスを表現する数理計画問題をgurobipyで実装

使用例:
    from torus import torus
    from draw_torus import draw_torus

    # グラフの定義
    V = [0, 1, 2]  # ノード集合
    A = [(0, 1), (1, 2), (2, 0)]  # エッジ集合（サイクル）

    # 階層割当の最適化
    y_val, t_val, L = torus(V, A)

    # 結果の可視化
    draw_torus(V, A, L)

数理モデル:
    - 変数:
        y[v]: ノードvの階層
        t[u,v]: エッジ(u,v)がトーラス辺かどうか（バイナリ）
        L_max: 使用される最大階層数

    - 制約:
        1. 最大階層の定義: y[v] ≤ L_max for all v
        2. トーラス辺の定義: t[u,v]=1 ⇔ y[u]>y[v] (Big-M法)
        3. 通常辺の階層制約: t[u,v]=0 ⇒ y[v]≥y[u]+lam[(u,v)]
        4. トーラス辺が少なくとも1本存在

    - 目的関数:
        minimize: α*L_max + β*Σ w(u,v)*(y[v]-y[u]+M*t[u,v])
        階層数を最小化しつつ、エッジスパンも考慮
"""

import gurobipy as gp
from gurobipy import GRB
from create_gurobi_env import create_gurobi_env

from collections import defaultdict


def torus(V, A, w=None, lam=None, alpha=100, beta=1, gamma=1000):
    """
    トーラスを含む階層グラフの階層割当を最適化

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        w: エッジ重み dict[(int,int): float] (デフォルト: すべて1)
        lam: エッジの最小階層差 dict[(int,int): int] (デフォルト: すべて1)
        alpha: 階層数の重み (デフォルト: 100)
        beta: エッジスパンの重み (デフォルト: 1)
        gamma: トーラス辺数の重み (デフォルト: 1000)

    Returns:
        y_val: 各ノードの階層 dict[int: int]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]
        L: レイヤー集合 dict[int: list[int]]
    """

    # エッジの重複を除去
    A = list(set(A))

    # デフォルト値の設定
    if w is None:
        w = {(u, v): 1 for (u, v) in A}
    if lam is None:
        lam = {(u, v): 1 for (u, v) in A}

    n = len(V)
    M = n  # Big-M定数（十分大きな値）

    env = create_gurobi_env()

    with gp.Model(name="Torus_Layout", env=env) as m:

        # ========== 変数定義 ==========

        # y[v]: ノードvの階層（0からn-1の整数）
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=n - 1, name="y")

        # t[u,v]: エッジ(u,v)がトーラス辺なら1、通常辺なら0
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        # L_max: 使用される最大階層数
        L_max = m.addVar(vtype=GRB.INTEGER, lb=0, ub=n - 1, name="L_max")

        # ========== 制約 ==========

        # 1. 最大階層の定義
        m.addConstrs((y[v] <= L_max for v in V), name="max_layer")

        # 2. トーラス辺の定義（Big-M法）
        # t[u,v] = 1 ⇔ y[u] > y[v]

        # (a) y[u] - y[v] <= M * t[u,v]
        # t=0のとき y[u] <= y[v]、t=1のとき制約は緩い
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")

        # (b) y[u] - y[v] >= 1 - M * (1 - t[u,v])
        # t=1のとき y[u] >= y[v] + 1、t=0のとき制約は緩い
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )

        # 3. 通常辺の階層制約
        # t[u,v] = 0のとき、y[v] >= y[u] + lam[(u,v)]
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        # ========== 目的関数 ==========

        # 階層数を最小化しつつ、エッジスパンの分散とトーラス辺数も考慮
        obj = (
            alpha * L_max  # 階層数を最小化
            # + beta
            # * gp.quicksum(
            #     w[(u, v)] * (y[v] - y[u] + M * t[u, v]) for (u, v) in A
            # )  # エッジスパン
            + beta
            * gp.quicksum(
                w[(u, v)] * (y[v] - y[u] + M * t[u, v]) * (y[v] - y[u] + M * t[u, v])
                for (u, v) in A
            )  # エッジスパンの2乗（分散）
            + gamma
            * gp.quicksum(t[u, v] for (u, v) in A)  # トーラス辺の数を直接ペナルティ
        )

        m.setObjective(obj, GRB.MINIMIZE)

        # ========== 最適化実行 ==========

        m.optimize()

        # ========== 結果の取得 ==========

        y_val = {}
        t_val = {}

        if m.status == GRB.OPTIMAL:
            # 各ノードの階層を取得
            for v in V:
                y_val[v] = int(y[v].X)

            # 各エッジがトーラス辺かを取得
            for u, v in A:
                t_val[(u, v)] = t[u, v].X > 0.5

            # レイヤー集合を構築
            layer_dict = defaultdict(list)
            for v in V:
                layer_dict[y_val[v]].append(v)

        else:
            print(f"最適化失敗: ステータス = {m.status}")
            # デバッグ用に実行不可能な制約を計算
            m.computeIIS()
            print("実行不可能な制約:")
            for c in m.getConstrs():
                if c.IISConstr:
                    print(f"  {c.constrName}")

        return y_val, t_val, layer_dict
