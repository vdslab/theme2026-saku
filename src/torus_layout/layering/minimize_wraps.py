"""固定したレイヤー数でトーラス辺数を最小化する。"""

from dataclasses import dataclass

import gurobipy as gp
from gurobipy import GRB
from ..models import Node, Edge, Flags, Weights, Layers, LayerAssignmentResult
from .lib.solver import create_gurobi_env, optimize
from .lib.model import add_layer_variables_and_constraints
from .lib.results import has_assignment, read_assignment


@dataclass(frozen=True)
class FixedLayerSolve:
    assignment: LayerAssignmentResult
    torus_count: int | None
    status: int


def solve_fixed_layers(
    nodes: list[Node], edges: list[Edge], layer_count: int,
    minimum_spans: dict[Edge, int] | None = None,
) -> FixedLayerSolve:
    if layer_count < 1:
        raise ValueError("L must be a positive layer count")
    spans = dict.fromkeys(edges, 1) if minimum_spans is None else minimum_spans
    with create_gurobi_env() as env, gp.Model(name="Torus_Minimize_Torus_Edges", env=env) as model:
        y, t = add_layer_variables_and_constraints(model, nodes, edges, layer_count, spans)
        model.setObjective(gp.quicksum(t[u, v] for u, v in edges), GRB.MINIMIZE)
        optimize(model)
        ranks, flags = read_assignment(model, nodes, edges, y, t, report_failure=False)
        count = sum(flags.values()) if has_assignment(model) else None
        return FixedLayerSolve(
            LayerAssignmentResult(ranks, flags, model.Runtime, model.Status, model.Runtime),
            count, model.Status,
        )


def minimize_torus_edges(
    V: list[Node],
    A: list[Edge],
    L: int,
    w: Weights | None = None,
    lam: dict[Edge, int] | None = None,
) -> tuple[dict[Node, int], Flags, Layers, float, int | None]:
    result = solve_fixed_layers(V, list(set(A)), L, lam)
    assignment = result.assignment
    return (
        assignment.node_to_layer, assignment.torus_flags, assignment.layers,
        assignment.runtime, result.torus_count,
    )
