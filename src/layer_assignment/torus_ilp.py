import gurobipy as gp
from gurobipy import GRB
from src.lib.create_gurobi_env import create_gurobi_env

from collections import defaultdict


def torus_ilp(V, A, w=None, lam=None, alpha=100, beta=1, gamma=1000):
    """
    トーラスを含む階層グラフの階層割当を最適化
    目的関数で利用する分散をILP化した式

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
    M = n  # Big-M定数（ここではノード数）

    alpha = max(10, n * 0.5)  # ノード数に応じて調整
    beta = n  # エッジスパンの重要度を上げる

    # エッジごとの離散化距離集合 K_{uv} = {lambda_{uv}, lambda_{uv}+1, ..., M-1}
    K_uv = {}
    for u, v in A:
        lo = lam[(u, v)] if (u, v) in lam else 1
        if lo < M:
            K_uv[(u, v)] = list(range(lo, M))
        else:
            K_uv[(u, v)] = []

    env = create_gurobi_env()

    with gp.Model(name="Torus_ILP", env=env) as m:

        # ========== 変数定義 (ILP) ==========

        # y[v]: ノードvの階層（0からn-1の整数）
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=n - 1, name="y")

        # L_max: 使用される最大階層数
        L_max = m.addVar(vtype=GRB.INTEGER, lb=0, ub=n - 1, name="L_max")

        # t[u,v]: wrap (トーラスをまたぐ) フラグ
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        # x[u,v,k]: one-hot 表示 (edge (u,v) の距離が k)
        x_keys = [(u, v, k) for (u, v) in A for k in K_uv[(u, v)]]
        if len(x_keys) > 0:
            x = m.addVars(x_keys, vtype=GRB.BINARY, name="x")
        else:
            x = {}

        # ========== 制約 ==========

        # (1) 各ノードの階層は L_max 以下
        m.addConstrs((y[v] <= L_max for v in V), name="max_layer")

        # (2) one-hot: 各エッジで距離選択はちょうど1つ（K_{uv} に対して）
        for u, v in A:
            if len(K_uv[(u, v)]) > 0:
                m.addConstr(
                    gp.quicksum(x[u, v, k] for k in K_uv[(u, v)]) == 1,
                    name=f"onehot_{u}_{v}",
                )
            else:
                # K_uv が空のエッジは one-hot を持たない（特殊扱い）
                pass

        # (4) 距離と y の関係: sum_k k*x = y_v - y_u + M*t
        # Note: K の総和は 1..M-1 の範囲を取り得るので RHS は正となる
        for u, v in A:
            if len(K_uv[(u, v)]) > 0:
                m.addConstr(
                    gp.quicksum(k * x[u, v, k] for k in K_uv[(u, v)])
                    == y[v] - y[u] + M * t[u, v],
                    name=f"distance_eq_{u}_{v}",
                )
            else:
                # K_uv が空のときは特殊制約（実質 y[v]-y[u]+M*t == 0）
                m.addConstr(
                    y[v] - y[u] + M * t[u, v] == 0, name=f"distance_emptyK_{u}_{v}"
                )

        # ===== Big-M 制約群（torus.py と同様の意味付け） =====
        # t[u,v] = 1 ⇔ y[u] > y[v]
        # (a) y[u] - y[v] <= M * t  (t=0 -> y[u] <= y[v])
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")

        # (b) y[u] - y[v] >= lam - M*(1 - t)  (t=1 -> y[u] >= y[v] + lam)
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )

        # (c) 通常辺の階層制約: t=0 のとき y[v] >= y[u] + lam
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        # (5) 対称性除去は行わない（元の `torus.py` と同じ振る舞いにする）

        # ========== 目的関数 ==========

        # エッジ距離の二乗は sum_k k^2 * x_{uvk} で表現可能（各エッジの K_{uv} を使う）
        edge_span_term = gp.quicksum(
            w[(u, v)] * gp.quicksum((k * k) * x[u, v, k] for k in K_uv[(u, v)])
            for (u, v) in A
            if len(K_uv[(u, v)]) > 0
        )

        obj = (
            alpha * L_max
            + beta * edge_span_term
            + gamma * gp.quicksum(t[u, v] for (u, v) in A)
        )

        m.setObjective(obj, GRB.MINIMIZE)

        # ========== 最適化実行 ==========

        m.optimize()

        # ========== 結果の取得 ==========

        y_val = {}
        t_val = {}
        chosen_k = {}

        if (
            m.status == GRB.OPTIMAL
            or m.status == GRB.TIME_LIMIT
            or m.status == GRB.SUBOPTIMAL
        ):
            for v in V:
                y_val[v] = int(round(y[v].X))

            for u, v in A:
                t_val[(u, v)] = int(round(t[u, v].X))
                if len(K_uv[(u, v)]) > 0:
                    sel_k = None
                    for k in K_uv[(u, v)]:
                        if x[u, v, k].X > 0.5:
                            sel_k = k
                            break
                    chosen_k[(u, v)] = sel_k

            layer_dict = defaultdict(list)
            for v in V:
                layer_dict[y_val[v]].append(v)
        else:
            print(f"最適化失敗: ステータス = {m.status}")
            m.computeIIS()
            print("実行不可能な制約:")
            for c in m.getConstrs():
                if c.IISConstr:
                    print(f"  {c.constrName}")

        run_time = m.Runtime

    return y_val, t_val, layer_dict, run_time
