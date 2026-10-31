"""4手法と辺数最小化で同一のBig-M制約。順序も元実装に合わせる。"""

import gurobipy as gp
from gurobipy import GRB
from ...models import Edge, Node


def add_layer_variables_and_constraints(
    model: gp.Model,
    nodes: list[Node],
    edges: list[Edge],
    layer_count: int,
    minimum_spans: dict[Edge, int],
    torus_count: int | None = None,
    *,
    continuous: bool = False,
) -> tuple[gp.tupledict[Node, gp.Var], gp.tupledict[Edge, gp.Var]]:
    maximum = layer_count - 1
    y = model.addVars(
        nodes,
        vtype=GRB.CONTINUOUS if continuous else GRB.INTEGER,
        lb=0,
        ub=maximum,
        name="y",
    )
    t = model.addVars(edges, vtype=GRB.BINARY, name="t")
    if torus_count is not None:
        model.addConstr(
            gp.quicksum(t[u, v] for u, v in edges) == torus_count,
            name="fixed_torus_count",
        )
    model.addConstrs((y[v] <= maximum for v in nodes), name="max_layer")
    model.addConstrs(
        (y[u] - y[v] <= layer_count * t[u, v] for u, v in edges), name="torus_def_a"
    )
    model.addConstrs(
        (
            y[u] - y[v] >= minimum_spans[u, v] - layer_count * (1 - t[u, v])
            for u, v in edges
        ),
        name="torus_def_b",
    )
    model.addConstrs(
        (y[v] - y[u] >= minimum_spans[u, v] - layer_count * t[u, v] for u, v in edges),
        name="normal_edge_constraint",
    )
    return y, t
