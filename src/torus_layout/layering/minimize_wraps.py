"""固定したレイヤー数でトーラス辺数を最小化する。"""
from collections import defaultdict
import gurobipy as gp
from gurobipy import GRB
from ..models import Node, Edge, Flags, Weights, Layers
from .lib.solver import create_gurobi_env

def _build_layer_dict(y_val: dict[Node, int]) -> Layers:
    layer_dict: Layers = defaultdict(list)
    for node, layer in y_val.items():
        layer_dict[layer].append(node)
    return layer_dict

def _prepare_edge_params(A: list[Edge], w: Weights | None=None, lam: dict[Edge, int] | None=None) -> tuple[Weights, dict[Edge, int]]:
    if w is None:
        w = {(u, v): 1 for u, v in A}
    if lam is None:
        lam = {(u, v): 1 for u, v in A}
    return (w, lam)

def minimize_torus_edges(V: list[Node], A: list[Edge], L: int, w: Weights | None=None, lam: dict[Edge, int] | None=None) -> tuple[dict[Node, int], Flags, Layers, float, int | None]:
    """
    L 個のレイヤー上でトーラス辺数を最小化する定式化。

    レイヤー番号は 0, ..., L - 1、トーラス周期は L とする。
    """
    if L < 1:
        raise ValueError('L must be a positive layer count')
    A = list(set(A))
    w, lam = _prepare_edge_params(A, w, lam)
    M = L
    env = create_gurobi_env()
    with gp.Model(name='Torus_Minimize_Torus_Edges', env=env) as m:
        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, ub=L - 1, name='y')
        t = m.addVars(A, vtype=GRB.BINARY, name='t')
        m.addConstrs((y[v] <= L - 1 for v in V), name='max_layer')
        m.addConstrs((y[u] - y[v] <= M * t[u, v] for u, v in A), name='torus_def_a')
        m.addConstrs((y[u] - y[v] >= lam[u, v] - M * (1 - t[u, v]) for u, v in A), name='torus_def_b')
        m.addConstrs((y[v] - y[u] >= lam[u, v] - M * t[u, v] for u, v in A), name='normal_edge_constraint')
        obj = gp.quicksum((t[u, v] for u, v in A))
        m.setObjective(obj, GRB.MINIMIZE)
        m.optimize()
        y_val: dict[Node, int] = {}
        t_val: Flags = {}
        layer_dict: Layers = {}
        torus_count: int | None = None
        if m.status == GRB.OPTIMAL or m.status == GRB.TIME_LIMIT or m.status == GRB.SUBOPTIMAL:
            for v in V:
                y_val[v] = int(round(y[v].X))
            for u, v in A:
                t_val[u, v] = t[u, v].X > 0.5
            layer_dict: Layers = _build_layer_dict(y_val)
            torus_count: int | None = sum((1 for u, v in A if t_val[u, v]))
        run_time = m.Runtime
    return (y_val, t_val, layer_dict, run_time, torus_count)

