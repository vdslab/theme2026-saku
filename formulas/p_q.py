import gurobipy as gp
from gurobipy import GRB

from longest_path import longest_path

from create_gurobi_env import create_gurobi_env


def pq(label, V, A, w, lam, V0, Vl):
    env = create_gurobi_env()
    val = {}

    with gp.Model(name=label, env=env) as m:

        l = longest_path(V, A)

        x = m.addVars(V, vtype=GRB.INTEGER, lb=0, name="y")

        m.addConstrs(
            (x[v] - x[u] >= lam[(u, v)] for (u, v) in A), name="diff_constraint"
        )

        m.addConstrs((x[v] == 0 for v in V0), name="V0_constraint")
        m.addConstrs((x[v] == l for v in Vl), name="Vl_constraint")

        m.setObjective(
            gp.quicksum(w[(u, v)] * ((x[v] - x[u]) ** 2) for (u, v) in A), GRB.MINIMIZE
        )
        m.optimize()

        if m.status == GRB.OPTIMAL:
            for v in V:
                val[v] = int(x[v].X)

    return val
