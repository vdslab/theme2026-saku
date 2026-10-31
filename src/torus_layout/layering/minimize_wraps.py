"""固定したレイヤー数でトーラス辺数を最小化する。"""

import gurobipy as gp
from gurobipy import GRB
from ..models import Node, Edge, Flags, Weights, Layers, LayerAssignmentResult
from .lib.solver import create_gurobi_env
from .lib.model import add_layer_variables_and_constraints
from .lib.results import read_assignment


def minimize_torus_edges(
    V: list[Node],
    A: list[Edge],
    L: int,
    w: Weights | None = None,
    lam: dict[Edge, int] | None = None,
) -> tuple[dict[Node, int], Flags, Layers, float, int | None]:
    if L < 1:
        raise ValueError("L must be a positive layer count")
    edges = list(set(A))
    spans = {edge: 1 for edge in edges} if lam is None else lam
    env = create_gurobi_env()
    with gp.Model(name="Torus_Minimize_Torus_Edges", env=env) as model:
        y, t = add_layer_variables_and_constraints(model, V, edges, L, spans)
        model.setObjective(gp.quicksum(t[u, v] for u, v in edges), GRB.MINIMIZE)
        model.optimize()
        ranks, flags = read_assignment(model, V, edges, y, t, report_failure=False)
        count = (
            sum(1 for edge in edges if flags[edge])
            if model.status in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL)
            else None
        )
        result = LayerAssignmentResult(ranks, flags, model.Runtime)
        return ranks, flags, result.layers, result.runtime, count
