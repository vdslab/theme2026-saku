"""
トーラス辺最小化とバランス最適化を2段階で行う定式化
"""

import os
import sys
from collections import defaultdict

import gurobipy as gp
from gurobipy import GRB

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.create_gurobi_env import create_gurobi_env


def _build_layer_dict(y_val):
    layer_dict = defaultdict(list)
    for node, layer in y_val.items():
        layer_dict[layer].append(node)
    return layer_dict


def _prepare_edge_params(A, w=None, lam=None):
    if w is None:
        w = {(u, v): 1 for (u, v) in A}
    if lam is None:
        lam = {(u, v): 1 for (u, v) in A}
    return w, lam


def minimize_torus_edges(V, A, L, w=None, lam=None):
    """
    L 個のレイヤー上でトーラス辺数を最小化する定式化。

    レイヤー番号は 0, ..., L - 1、トーラス周期は L とする。
    """
    if L < 1:
        raise ValueError("L must be a positive layer count")

    A = list(set(A))
    w, lam = _prepare_edge_params(A, w, lam)
    M = L  # Big-M定数とトーラス周期

    env = create_gurobi_env()

    with gp.Model(name="Torus_Minimize_Torus_Edges", env=env) as m:
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=L - 1, name="y")
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        m.addConstrs((y[v] <= L - 1 for v in V), name="max_layer")
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        obj = gp.quicksum(t[u, v] for (u, v) in A)
        m.setObjective(obj, GRB.MINIMIZE)

        m.optimize()

        y_val = {}
        t_val = {}
        layer_dict = {}
        torus_count = None

        if (
            m.status == GRB.OPTIMAL
            or m.status == GRB.TIME_LIMIT
            or m.status == GRB.SUBOPTIMAL
        ):
            for v in V:
                y_val[v] = int(round(y[v].X))
            for u, v in A:
                t_val[(u, v)] = t[u, v].X > 0.5
            layer_dict = _build_layer_dict(y_val)
            torus_count = sum(1 for (u, v) in A if t_val[(u, v)])

        run_time = m.Runtime

    return y_val, t_val, layer_dict, run_time, torus_count


def balance_with_fixed_torus_edges(V, A, L, torus_count, w=None, lam=None):
    """
    L 個のレイヤーとトーラス辺数を固定し、エッジスパンの二乗和を最小化する。
    """
    if L < 1:
        raise ValueError("L must be a positive layer count")

    A = list(set(A))
    w, lam = _prepare_edge_params(A, w, lam)
    M = L  # Big-M定数とトーラス周期

    K_uv = {}
    for u, v in A:
        lo = lam[(u, v)] if (u, v) in lam else 1
        if lo < M:
            K_uv[(u, v)] = list(range(lo, M))
        else:
            K_uv[(u, v)] = []

    env = create_gurobi_env()

    with gp.Model(name="Torus_Balance_With_Fixed_Torus", env=env) as m:
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=L - 1, name="y")
        t = m.addVars(A, vtype=GRB.BINARY, name="t")

        x_keys = [(u, v, k) for (u, v) in A for k in K_uv[(u, v)]]
        x = m.addVars(x_keys, vtype=GRB.BINARY, name="x") if x_keys else {}

        m.addConstrs((y[v] <= L - 1 for v in V), name="max_layer")
        m.addConstr(
            gp.quicksum(t[u, v] for (u, v) in A) == torus_count,
            name="fixed_torus_count",
        )

        for u, v in A:
            if len(K_uv[(u, v)]) > 0:
                m.addConstr(
                    gp.quicksum(x[u, v, k] for k in K_uv[(u, v)]) == 1,
                    name=f"onehot_{u}_{v}",
                )
            else:
                pass

        for u, v in A:
            if len(K_uv[(u, v)]) > 0:
                m.addConstr(
                    gp.quicksum(k * x[u, v, k] for k in K_uv[(u, v)])
                    == y[v] - y[u] + M * t[u, v],
                    name=f"distance_eq_{u}_{v}",
                )
            else:
                m.addConstr(
                    y[v] - y[u] + M * t[u, v] == 0, name=f"distance_emptyK_{u}_{v}"
                )

        m.addConstrs((y[u] - y[v] <= M * t[u, v] for (u, v) in A), name="torus_def_a")
        m.addConstrs(
            (y[u] - y[v] >= lam[(u, v)] - M * (1 - t[u, v]) for (u, v) in A),
            name="torus_def_b",
        )
        m.addConstrs(
            (y[v] - y[u] >= lam[(u, v)] - M * t[u, v] for (u, v) in A),
            name="normal_edge_constraint",
        )

        edge_span_term = gp.quicksum(
            w[(u, v)] * gp.quicksum((k * k) * x[u, v, k] for k in K_uv[(u, v)])
            for (u, v) in A
            if len(K_uv[(u, v)]) > 0
        )

        m.setObjective(edge_span_term, GRB.MINIMIZE)
        m.optimize()

        y_val = {}
        t_val = {}
        layer_dict = {}

        if (
            m.status == GRB.OPTIMAL
            or m.status == GRB.TIME_LIMIT
            or m.status == GRB.SUBOPTIMAL
        ):
            for v in V:
                y_val[v] = int(round(y[v].X))
            for u, v in A:
                t_val[(u, v)] = t[u, v].X > 0.5
            layer_dict = _build_layer_dict(y_val)

        run_time = m.Runtime

    return y_val, t_val, layer_dict, run_time


def torus_two_stage_with_diameter(V, A, L, w=None, lam=None):
    """
    直径ベースのLを使い、トーラス辺最小化 -> バランス最小化の2段階で解く
    """
    A = list(set(A))

    step1 = minimize_torus_edges(V, A, L, w=w, lam=lam)
    y_val, t_val, layer_dict, runtime_1, torus_count = step1

    if not y_val:
        return {
            "success": False,
            "L": L,
            "torus_count": None,
            "step1_runtime": runtime_1,
            "step2_runtime": None,
        }

    step2 = balance_with_fixed_torus_edges(V, A, L, torus_count, w=w, lam=lam)
    y_val2, t_val2, layer_dict2, runtime_2 = step2
    if not y_val2:
        return {
            "success": False,
            "L": L,
            "torus_count": torus_count,
            "step1_runtime": runtime_1,
            "step2_runtime": runtime_2,
        }

    return {
        "success": True,
        "L": L,
        "torus_count": torus_count,
        "y_val": y_val2,
        "t_val": t_val2,
        "layer_dict": layer_dict2,
        "step1_runtime": runtime_1,
        "step2_runtime": runtime_2,
    }


if __name__ == "__main__":
    from lib.generate_torus_graph import generate_cyclic_graph

    V, A = generate_cyclic_graph(n=18, num_cycles=2, edge_prob=0.01, seed=42)
    result = torus_two_stage_with_diameter(V, A)

    print(f"success: {result['success']}")
    print(f"L (diameter): {result['L']}")
    print(f"torus_count: {result['torus_count']}")
    if result["success"]:
        max_layer = max(result["y_val"].values()) if result["y_val"] else None
        print(f"max_layer: {max_layer}")
        print(
            f"runtime: step1={result['step1_runtime']:.4f}, step2={result['step2_runtime']:.4f}"
        )
