import gurobipy as gp
from gurobipy import GRB

from longest_path import longest_path

from create_gurobi_env import create_gurobi_env


def pl(label, V, A, w, lam, V0, Vl):
    env = create_gurobi_env()
    val = {}

    with gp.Model(name=label, env=env) as m:

        l = longest_path(V, A)

        K = {}
        for s, t in A:
            K[(s, t)] = list(range(lam[(s, t)], l + 1))

        y = m.addVars(V, vtype=GRB.INTEGER, lb=0, name="y")

        x_keys = [(u, v, k) for (u, v) in A for k in K[(u, v)]]
        x = m.addVars(x_keys, vtype=GRB.BINARY, name="x")

        m.addConstrs(
            (
                (gp.quicksum(k * x[u, v, k] for k in K[(u, v)]) - y[v] + y[u] == 0)
                for (u, v) in A
            ),
            name="flow_eq",
        )

        m.addConstrs(
            ((gp.quicksum(x[u, v, k] for k in K[(u, v)]) == 1) for (u, v) in A),
            name="one_choice",
        )

        m.addConstrs((y[v] == 0 for v in V0), name="V0_constraint")
        m.addConstrs((y[v] == l for v in Vl), name="Vl_constraint")

        obj = gp.quicksum(
            w[(u, v)] * gp.quicksum((k**2) * x[u, v, k] for k in K[(u, v)])
            for (u, v) in A
        )
        m.setObjective(obj, GRB.MINIMIZE)

        m.optimize()

        if m.status == GRB.OPTIMAL:
            for v in V:
                val[v] = int(y[v].X)

    return val
