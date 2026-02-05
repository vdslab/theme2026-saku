import itertools
import gurobipy as gp
from gurobipy import GRB

from create_gurobi_env import create_gurobi_env


def intersection_reduction(V_layers, E_layers, w):
    env = create_gurobi_env()

    x_val = {}
    c_val = {}

    with gp.Model(env=env) as m:

        x = {}
        for k, nodes in V_layers.items():
            for u1, u2 in itertools.permutations(nodes, 2):
                x[(u1, u2)] = m.addVar(vtype=GRB.BINARY, name=f"x_{u1}_{u2}")

        for k, nodes in V_layers.items():
            for u1, u2 in itertools.combinations(nodes, 2):
                m.addConstr(x[(u1, u2)] + x[(u2, u1)] == 1, name=f"order_{u1}_{u2}")

        for k, nodes in V_layers.items():
            for u1, u2, u3 in itertools.permutations(nodes, 3):
                if u1 != u2 and u2 != u3 and u1 != u3:
                    m.addConstr(
                        x[(u3, u1)] >= x[(u3, u2)] + x[(u2, u1)] - 1,
                        name=f"trans_{u3}_{u2}_{u1}",
                    )

        c = {}
        for k, edges in E_layers.items():
            for e1, e2 in itertools.combinations(edges, 2):
                key = (e1, e2)
                c[key] = m.addVar(vtype=GRB.BINARY, name=f"c_{e1}_{e2}")

                u1, v1 = e1
                u2, v2 = e2
                if u1 != u2 and v1 != v2:
                    m.addConstr(
                        c[key] + x[(u2, u1)] + x[(v1, v2)] >= 1,
                        name=f"c4_{u1}_{v1}_{u2}_{v2}",
                    )
                    m.addConstr(
                        c[key] + x[(u1, u2)] + x[(v2, v1)] >= 1,
                        name=f"c5_{u1}_{v1}_{u2}_{v2}",
                    )

        for k, edges in E_layers.items():
            edge_set = set(edges)
            nodes_left = V_layers.get(k, [])
            nodes_right = V_layers.get(k + 1, [])
            for u1, u2 in itertools.combinations(nodes_left, 2):
                for v1, v2 in itertools.combinations(nodes_right, 2):
                    e_a = (u1, v1)
                    e_b = (u1, v2)
                    e_c = (u2, v1)
                    e_d = (u2, v2)
                    if (
                        e_a in edge_set
                        and e_b in edge_set
                        and e_c in edge_set
                        and e_d in edge_set
                    ):
                        key1 = (e_a, e_d) if (e_a, e_d) in c else (e_d, e_a)
                        key2 = (e_b, e_c) if (e_b, e_c) in c else (e_c, e_b)
                        if key1 in c and key2 in c:
                            m.addConstr(
                                c[key1] + c[key2] == 1, name=f"four_{u1}_{u2}_{v1}_{v2}"
                            )

        obj_terms = []
        for (e1, e2), var in c.items():
            obj_terms.append(w.get(e1, 1.0) * w.get(e2, 1.0) * var)

        m.setObjective(gp.quicksum(obj_terms), GRB.MINIMIZE)

        try:
            for var in x.values():
                var.BranchPriority = 10
            for var in c.values():
                var.BranchPriority = 1
        except Exception:
            pass

        m.optimize()

        x_val = {key: var.X for key, var in x.items()}
        c_val = {key: var.X for key, var in c.items()}

    return x_val, c_val
