"""
トーラス辺数とレイヤー数を固定してバランスを取る階層割当関数

4つの最適化手法を提供:
1. diff: エッジスパンの和を最小化 (ILP)
2. diff_square: エッジスパンの2乗和を最小化 (IQP)
3. qp: 連続緩和版 (QP + 四捨五入)
4. barycenter: 反復的重心法 (ヒューリスティック)
"""

import time
from collections import defaultdict
import gurobipy as gp
from gurobipy import GRB
from lib.create_gurobi_env import create_gurobi_env


def _prepare_params(A, w, lam):
    """パラメータの準備"""
    A = list(set(A))
    if w is None:
        w = {(u, v): 1 for (u, v) in A}
    if lam is None:
        lam = {(u, v): 1 for (u, v) in A}
    return A, w, lam


def _build_layer_dict(y_val):
    """レイヤー辞書の構築"""
    layer_dict = defaultdict(list)
    for node, layer in y_val.items():
        layer_dict[layer].append(node)
    return dict(layer_dict)


def _optimize_diff(V, A, torus_count, layer_count, w, lam):
    """
    手法1: エッジスパンの和を最小化 (ILP)
    目的関数: minimize Σ w[u,v] * (y[v] - y[u] + M*t[u,v])
    """
    if layer_count < 1:
        raise ValueError("layer_count must be positive")
    M = layer_count
    max_layer = layer_count - 1
    env = create_gurobi_env()

    with gp.Model(name="Torus_Balance_Diff", env=env) as m:
        # 変数定義
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=max_layer, name="y")
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        # 制約
        # トーラス辺数固定
        m.addConstr(
            gp.quicksum(t[u, v] for (u, v) in A) == torus_count,
            name="fixed_torus_count",
        )

        # レイヤー数固定
        m.addConstrs((y[v] <= max_layer for v in V), name="max_layer")

        # Big-M制約（トーラス辺の定義）
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        # 目的関数: エッジスパンの和
        obj = gp.quicksum(w[(u, v)] * (y[v] - y[u] + M * t[u, v]) for (u, v) in A)
        m.setObjective(obj, GRB.MINIMIZE)

        m.optimize()

        # 結果取得
        y_val = {}
        t_val = {}
        if m.status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL]:
            for v in V:
                y_val[v] = int(round(y[v].X))
            for u, v in A:
                t_val[(u, v)] = t[u, v].X > 0.5
        else:
            print(f"最適化失敗: ステータス = {m.status}")

        return y_val, t_val, m.Runtime


def _optimize_diff_square(V, A, torus_count, layer_count, w, lam):
    """
    手法2: エッジスパンの2乗和を最小化 (IQP)
    目的関数: minimize Σ w[u,v] * (y[v] - y[u] + M*t[u,v])²
    """
    if layer_count < 1:
        raise ValueError("layer_count must be positive")
    M = layer_count
    max_layer = layer_count - 1
    env = create_gurobi_env()

    with gp.Model(name="Torus_Balance_DiffSquare", env=env) as m:
        # 変数定義
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=max_layer, name="y")
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        # 制約
        m.addConstr(
            gp.quicksum(t[u, v] for (u, v) in A) == torus_count,
            name="fixed_torus_count",
        )
        m.addConstrs((y[v] <= max_layer for v in V), name="max_layer")
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        # 目的関数: エッジスパンの2乗和
        obj = gp.quicksum(
            w[(u, v)] * (y[v] - y[u] + M * t[u, v]) * (y[v] - y[u] + M * t[u, v])
            for (u, v) in A
        )
        m.setObjective(obj, GRB.MINIMIZE)

        m.optimize()

        # 結果取得
        y_val = {}
        t_val = {}
        if m.status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL]:
            for v in V:
                y_val[v] = int(round(y[v].X))
            for u, v in A:
                t_val[(u, v)] = t[u, v].X > 0.5
        else:
            print(f"最適化失敗: ステータス = {m.status}")

        return y_val, t_val, m.Runtime


def _optimize_qp(V, A, torus_count, layer_count, w, lam):
    """
    手法3: 連続緩和版 (QP + 四捨五入)
    y[v]のみ連続変数、t[u,v]はバイナリ
    目的関数: minimize Σ w[u,v] * (y[v] - y[u] + M*t[u,v])²
    """
    if layer_count < 1:
        raise ValueError("layer_count must be positive")
    M = layer_count
    max_layer = layer_count - 1
    env = create_gurobi_env()

    with gp.Model(name="Torus_Balance_QP", env=env) as m:
        # 変数定義: y[v]は連続変数
        y = m.addVars(V, vtype=GRB.CONTINUOUS, lb=0, ub=max_layer, name="y")
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        # 制約
        m.addConstr(
            gp.quicksum(t[u, v] for (u, v) in A) == torus_count,
            name="fixed_torus_count",
        )
        m.addConstrs((y[v] <= max_layer for v in V), name="max_layer")
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        # 目的関数: エッジスパンの2乗和
        obj = gp.quicksum(
            w[(u, v)] * (y[v] - y[u] + M * t[u, v]) * (y[v] - y[u] + M * t[u, v])
            for (u, v) in A
        )
        m.setObjective(obj, GRB.MINIMIZE)

        m.optimize()

        # 結果取得（四捨五入）
        y_val = {}
        t_val = {}
        if m.status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL]:
            for v in V:
                y_val[v] = int(round(y[v].X))  # 四捨五入
            for u, v in A:
                t_val[(u, v)] = t[u, v].X > 0.5
        else:
            print(f"最適化失敗: ステータス = {m.status}")

        return y_val, t_val, m.Runtime


def _optimize_barycenter(V, A, torus_count, layer_count, w, lam):
    """
    手法4: 反復的重心法 (ヒューリスティック)

    アルゴリズム:
    1. 初期解: Gurobi (diff_square) で制約を満たす解を取得
    2. 反復: 各頂点を移動可能範囲内で走査し、最も重心が整っている位置に移動
    3. 停止条件: 変化量が閾値未満

    移動可能範囲:
    - ノードxについて
    - xに入る全てのエッジの根本のノードよりも左に行ってはいけない
    - xから出る全てのエッジの先端のノードよりも右に行ってはいけない
    """
    max_layer_bound = layer_count - 1

    # 初期解を取得
    y_val, t_val, init_time = _optimize_diff(V, A, torus_count, layer_count, w, lam)

    if not y_val:
        return y_val, t_val, init_time

    start_time = time.time()

    # 初期解で同一階層のエッジをチェックし、修正
    for u, v in A:
        if not t_val[(u, v)] and y_val[u] == y_val[v]:
            # 通常辺なのに同一階層にいる場合、vを1つ右に移動
            if y_val[v] < max_layer_bound:
                y_val[v] += 1
            elif y_val[u] > 0:
                y_val[u] -= 1

    # 入力エッジと出力エッジを分離
    in_edges = defaultdict(list)  # ノードvに入るエッジの始点リスト
    out_edges = defaultdict(list)  # ノードuから出るエッジの終点リスト

    for u, v in A:
        in_edges[v].append(u)  # vに入るエッジの根本 = u
        out_edges[u].append(v)  # uから出るエッジの先端 = v

    # 反復パラメータ
    threshold = 0.01  # 変化量の閾値
    max_iterations = 100  # 最大反復回数

    iteration = 0
    while iteration < max_iterations:
        total_change = 0.0
        new_y_val = y_val.copy()

        # 各頂点について最適位置を探索
        for v in V:
            # 移動可能範囲を計算
            # 左側の制約: vに入るエッジの根本のノードの最大階層より左に行けない
            if v in in_edges and len(in_edges[v]) > 0:
                min_layer = max(y_val[u] for u in in_edges[v]) + 1
            else:
                min_layer = 0

            # 右側の制約: vから出るエッジの先端のノードの最小階層より右に行けない
            if v in out_edges and len(out_edges[v]) > 0:
                max_layer = min(y_val[u] for u in out_edges[v]) - 1
            else:
                max_layer = max_layer_bound

            # 全体の制約も考慮
            min_layer = max(min_layer, 0)
            max_layer = min(max_layer, max_layer_bound)

            # 移動可能範囲が無効な場合は現在位置を維持
            if min_layer > max_layer:
                continue

            # 移動可能範囲内で走査し、最も重心が整っている位置を探す

            # 全隣接ノードを取得（チェックに使用）
            all_neighbors = []
            if v in in_edges:
                all_neighbors.extend(in_edges[v])
            if v in out_edges:
                all_neighbors.extend(out_edges[v])

            if len(all_neighbors) == 0:
                continue

            # 重心（隣接ノードの平均階層）を直接計算
            # 数学的に、Σ(y_val[u] - c)² を最小化する c は平均値
            center = sum(y_val[u] for u in all_neighbors) / len(all_neighbors)

            # 整数に丸める
            candidate_layer = round(center)

            # 移動可能範囲でクランプ
            candidate_layer = max(min_layer, min(max_layer, candidate_layer))

            # 同一階層チェック：隣接ノードと同じ階層になる場合は調整
            if any(y_val[u] == candidate_layer for u in all_neighbors):
                # 候補位置から上下に探索して、同一階層にならない最も近い位置を探す
                found = False
                for offset in range(1, max_layer - min_layer + 2):
                    # 上方向を試す
                    upper = candidate_layer + offset
                    if upper <= max_layer and not any(
                        y_val[u] == upper for u in all_neighbors
                    ):
                        candidate_layer = upper
                        found = True
                        break
                    # 下方向を試す
                    lower = candidate_layer - offset
                    if lower >= min_layer and not any(
                        y_val[u] == lower for u in all_neighbors
                    ):
                        candidate_layer = lower
                        found = True
                        break

                # 見つからない場合は現在位置を維持
                if not found:
                    candidate_layer = y_val[v]

            best_layer = candidate_layer

            # 変化量を記録
            total_change += abs(best_layer - y_val[v])
            new_y_val[v] = best_layer

        # 更新
        y_val = new_y_val

        # 同一階層のエッジをチェックし、修正（ポストプロセス）
        for u, v in A:
            if not t_val[(u, v)] and y_val[u] == y_val[v]:
                # 通常辺なのに同一階層にいる場合、vを移動
                # vから出るエッジの先端より右に移動できるかチェック
                if v in out_edges and len(out_edges[v]) > 0:
                    min_v_layer = min(y_val[w] for w in out_edges[v])
                    if y_val[v] + 1 < min_v_layer:
                        y_val[v] += 1
                        continue
                # uに入るエッジの根本より左に移動できるかチェック
                if u in in_edges and len(in_edges[u]) > 0:
                    max_u_layer = max(y_val[w] for w in in_edges[u])
                    if y_val[u] - 1 > max_u_layer:
                        y_val[u] -= 1
                        continue
                # どちらもダメなら、vを右に（制約無視）
                if y_val[v] < max_layer_bound:
                    y_val[v] += 1
                elif y_val[u] > 0:
                    y_val[u] -= 1

        iteration += 1

        # 収束判定
        if total_change < threshold:
            break

    heuristic_time = time.time() - start_time
    total_time = init_time + heuristic_time

    return y_val, t_val, total_time


def balance_layer_assignment(
    V, A, torus_count, layer_count, func_type, w=None, lam=None
):
    """
    トーラス辺数とレイヤー数を固定してバランスを取る階層割当関数

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        torus_count: トーラス辺数（固定値） int
        layer_count: レイヤー数（固定値） int。番号は 0..layer_count-1
        func_type: 最適化手法の識別子 str
            - "diff": エッジスパンの和を最小化 (ILP)
            - "diff_square": エッジスパンの2乗和を最小化 (IQP)
            - "qp": 連続緩和版 (QP + 四捨五入)
            - "barycenter": 反復的重心法 (ヒューリスティック)
        w: エッジ重み dict[(int,int): float] (オプション)
        lam: エッジの最小階層差 dict[(int,int): int] (オプション)

    Returns:
        y_val: 各ノードの階層 dict[int: int]
        t_val: 各エッジがトーラス辺か dict[(int,int): bool]
        layer_dict: レイヤー集合 dict[int: list[int]]
        run_time: 実行時間 float
    """
    # パラメータ準備
    A, w, lam = _prepare_params(A, w, lam)

    # 手法に応じて最適化
    if func_type == "diff":
        y_val, t_val, run_time = _optimize_diff(V, A, torus_count, layer_count, w, lam)
    elif func_type == "diff_square":
        y_val, t_val, run_time = _optimize_diff_square(
            V, A, torus_count, layer_count, w, lam
        )
    elif func_type == "qp":
        y_val, t_val, run_time = _optimize_qp(V, A, torus_count, layer_count, w, lam)
    elif func_type == "barycenter":
        y_val, t_val, run_time = _optimize_barycenter(
            V, A, torus_count, layer_count, w, lam
        )
    else:
        raise ValueError(f"Unknown func_type: {func_type}")

    # レイヤー辞書を構築
    layer_dict = _build_layer_dict(y_val) if y_val else {}

    return y_val, t_val, layer_dict, run_time
