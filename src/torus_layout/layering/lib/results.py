"""ソルバー結果を元と同じ終了条件・丸めで取得する。"""

import gurobipy as gp
from gurobipy import GRB
from ...models import Edge, Node, Flags


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
    if model.status in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
        for node in nodes:
            ranks[node] = int(round(y[node].X))
        for source, target in edges:
            flags[source, target] = t[source, target].X > 0.5
    elif report_failure:
        print(f"最適化失敗: ステータス = {model.status}")
    return ranks, flags
