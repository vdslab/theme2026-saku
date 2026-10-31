"""有向辺の周期スパンの重み付き和を最小化するILP。"""
from ...models import Node, Edge, Flags, Weights
from ..lib.solver import create_gurobi_env
import gurobipy as gp
from gurobipy import GRB

def _optimize_diff(V: list[Node], A: list[Edge], torus_count: int, layer_count: int, w: Weights, lam: dict[Edge, int]) -> tuple[dict[Node, int], Flags, float]:
    """
    手法1: エッジスパンの和を最小化 (ILP)
    目的関数: minimize Σ w[u,v] * (y[v] - y[u] + M*t[u,v])
    """
    if layer_count < 1:
        raise ValueError('layer_count must be positive')
    M = layer_count
    max_layer = layer_count - 1
    env = create_gurobi_env()
    with gp.Model(name='Torus_Balance_Diff', env=env) as m:
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=max_layer, name='y')
        t = m.addVars(A, vtype=GRB.BINARY, name='t')
        m.addConstr(gp.quicksum((t[u, v] for u, v in A)) == torus_count, name='fixed_torus_count')
        m.addConstrs((y[v] <= max_layer for v in V), name='max_layer')
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for u, v in A), name='torus_def_a')
        m.addConstrs((y[u] - y[v] >= lam[u, v] - M * (1 - t[u, v]) for u, v in A), name='torus_def_b')
        m.addConstrs((y[v] - y[u] >= lam[u, v] - M * t[u, v] for u, v in A), name='normal_edge_constraint')
        obj = gp.quicksum((w[u, v] * (y[v] - y[u] + M * t[u, v]) for u, v in A))
        m.setObjective(obj, GRB.MINIMIZE)
        m.optimize()
        y_val: dict[Node, int] = {}
        t_val: Flags = {}
        if m.status in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL]:
            for v in V:
                y_val[v] = int(round(y[v].X))
            for u, v in A:
                t_val[u, v] = t[u, v].X > 0.5
        else:
            print(f'最適化失敗: ステータス = {m.status}')
        return (y_val, t_val, m.Runtime)

