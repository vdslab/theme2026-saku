"""Experimental MILP for the integer squared-span objective."""

import gurobipy as gp
from gurobipy import GRB
from torus_layout.layering.lib.model import add_layer_variables_and_constraints
from torus_layout.layering.lib.results import read_assignment
from torus_layout.layering.lib.solver import create_gurobi_env
from torus_layout.models import LayerAssignmentResult


def optimize_square_epigraph(graph, layer_count, torus_count, *, start=None):
    nodes = list(graph.nodes)
    edges = list(dict.fromkeys(graph.edges))
    minimum = dict.fromkeys(edges, 1)
    with create_gurobi_env() as env, gp.Model("Torus_Balance_DiffSquareMILP", env=env) as model:
        ranks, wraps = add_layer_variables_and_constraints(
            model, nodes, edges, layer_count, minimum, torus_count
        )
        costs = model.addVars(edges, lb=1, name="square")
        spans = {(u, v): ranks[v] - ranks[u] + layer_count * wraps[u, v] for u, v in edges}
        model.setObjective(costs.sum(), GRB.MINIMIZE)
        model.Params.LazyConstraints = 1

        if start is not None and start.node_to_layer:
            for node in nodes:
                ranks[node].Start = start.node_to_layer[node]
            for u, v in edges:
                edge = u, v
                wrapped = int(start.torus_flags[edge])
                wraps[edge].Start = wrapped
                span = start.node_to_layer[v] - start.node_to_layer[u] + layer_count * wrapped
                costs[edge].Start = span * span

        def separate(problem, where):
            if where != GRB.Callback.MIPSOL:
                return
            r = problem.cbGetSolution(ranks)
            t = problem.cbGetSolution(wraps)
            z = problem.cbGetSolution(costs)
            for u, v in edges:
                edge = u, v
                k = round(r[v]) - round(r[u]) + layer_count * round(t[edge])
                if z[edge] < k * k - 1e-5:
                    # The secant through consecutive integers underestimates every integer.
                    problem.cbLazy(costs[edge] >= (2 * k + 1) * spans[edge] - k * (k + 1))

        model.optimize(separate)
        y, t = read_assignment(model, nodes, edges, ranks, wraps)
        if model.SolCount:
            realized = sum((y[v] - y[u] + layer_count * t[u, v]) ** 2 for u, v in edges)
            if abs(model.ObjVal - realized) > 1e-4:
                raise RuntimeError("MILP incumbent does not realize its reported squared objective")
        return LayerAssignmentResult(y, t, model.Runtime, model.Status, model.Runtime)
