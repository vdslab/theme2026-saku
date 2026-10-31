"""連続緩和して四捨五入する二乗スパン最小化。"""
import gurobipy as gp
from gurobipy import GRB
from ...models import Node, Edge, Flags, Weights
from ..lib.solver import create_gurobi_env
from ..lib.model import add_layer_variables_and_constraints
from ..lib.results import read_assignment

def _optimize_qp(V: list[Node], A: list[Edge], torus_count: int,
                     layer_count: int, w: Weights, lam: dict[Edge,int]
                     ) -> tuple[dict[Node,int], Flags, float]:
    if layer_count < 1:
        raise ValueError("layer_count must be positive")
    env = create_gurobi_env()
    with gp.Model(name="Torus_Balance_QP", env=env) as model:
        y, t = add_layer_variables_and_constraints(model, V, A, layer_count, lam,
                                                   torus_count, continuous=True)
        objective = gp.quicksum(w[u,v] * (y[v]-y[u]+layer_count*t[u,v]) * (y[v]-y[u]+layer_count*t[u,v]) for u,v in A)
        model.setObjective(objective, GRB.MINIMIZE)
        model.optimize()
        ranks, flags = read_assignment(model, V, A, y, t)
        return ranks, flags, model.Runtime
