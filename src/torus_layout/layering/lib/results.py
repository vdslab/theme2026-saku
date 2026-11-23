"""取得可能なソルバー解を読み、元と同じ規則で丸める。"""

import gurobipy as gp
from gurobipy import GRB
from ...models import Edge, Node, Flags


def has_assignment(model: gp.Model) -> bool:
    return model.Status in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL) and model.SolCount > 0


def read_assignment(
    model: gp.Model,
    nodes: list[Node],
    edges: list[Edge],
    y: gp.tupledict[Node, gp.Var],
    t: gp.tupledict[Edge, gp.Var],
    *,
    report_failure: bool = True,
) -> tuple[dict[Node, int], Flags]:
    ranks: dict[Node, int] = {}
    flags: Flags = {}
    if has_assignment(model):
        for node in nodes:
            ranks[node] = int(round(y[node].X))
        for source, target in edges:
            flags[source, target] = t[source, target].X > 0.5
    elif report_failure:
        reason = {
            GRB.INFEASIBLE: "実行不能",
            GRB.TIME_LIMIT: "時間切れ（実行可能解なし）",
        }.get(model.Status, "実行可能解なし")
        print(f"最適化失敗: {reason} (status={model.Status})")
    return ranks, flags
