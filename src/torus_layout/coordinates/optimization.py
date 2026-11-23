"""Fixed-embedding toroidal LP/QP coordinate assignment (not planar BK).

Winding numbers and the cut order remain fixed. All edges, including horizontal
wraps, participate. The drawing uses end.y + psi * period in its universal cover.
"""

from .. import constants

from collections import defaultdict
import math
import gurobipy as gp
from ..models import Node, Edge, Layers, Positions, Weights
from ..domain import vertical_bounds
from ..layering.lib.solver import create_gurobi_env, optimize


def optimize_positions(
    initial: Positions,
    order: Layers,
    edges: list[Edge],
    psi: dict[Edge, int],
    weights: Weights,
    dummy_nodes: set[Node],
    period: float,
    min_gap: float,
    *,
    method: str,
    bend_weight: float = constants.DEFAULT_BEND_WEIGHT,
) -> Positions:
    """Minimize weighted lifted L1 or squared displacement plus dummy bends.

    Requires a proper layered graph for the bend term (unit horizontal spans).
    Only an OPTIMAL solve is accepted; license/solver failures are never hidden.
    The tiny domain margin keeps points off the renderer's open boundary.
    """
    if method not in ("torus_qp", "torus_lp"):
        raise ValueError(f"unknown coordinate method: {method!r}")
    if not math.isfinite(bend_weight) or bend_weight < 0:
        raise ValueError("bend_weight must be finite and non-negative")
    for edge in edges:
        if not math.isfinite(weights.get(edge, 1.0)) or weights.get(edge, 1.0) < 0:
            raise ValueError("coordinate weights must be finite and non-negative")
        if not isinstance(psi.get(edge, 0), int):
            raise ValueError("winding numbers must be integers")
    if not initial:
        return {}
    incoming: dict[Node, list[int]] = defaultdict(list)
    outgoing: dict[Node, list[int]] = defaultdict(list)
    for i, (u, v) in enumerate(edges):
        incoming[v].append(i)
        outgoing[u].append(i)
    with create_gurobi_env() as env, gp.Model(env=env) as model:
        model.Params.FeasibilityTol = constants.COORDINATE_FEASIBILITY_TOL
        model.Params.OptimalityTol = constants.COORDINATE_OPTIMALITY_TOL
        model.Params.BarConvTol = constants.COORDINATE_BARRIER_TOL
        margin = max(constants.COORDINATE_DOMAIN_MARGIN, min_gap * constants.COORDINATE_DOMAIN_MARGIN)
        lower, upper = vertical_bounds(period, max(map(len, order.values()), default=1))
        y = {node: model.addVar(lb=lower + margin, ub=upper - margin) for node in initial}
        for nodes in order.values():
            for u, v in zip(nodes, nodes[1:]):
                model.addConstr(y[v] - y[u] >= min_gap)
            if nodes:
                model.addConstr(y[nodes[-1]] - y[nodes[0]] <= period - min_gap)
        displacement = [y[v] - y[u] + psi.get((u, v), 0) * period
                        for u, v in edges]
        terms = [(delta, weights.get(edge, 1.0))
                 for edge, delta in zip(edges, displacement)]
        if bend_weight:
            for node in dummy_nodes:
                if len(incoming[node]) == len(outgoing[node]) == 1:
                    i, j = incoming[node][0], outgoing[node][0]
                    # After subdivision both segments have horizontal length 1.
                    terms.append((displacement[j] - displacement[i], bend_weight))
        if method == "torus_qp":
            objective = gp.quicksum(weight * delta * delta for delta, weight in terms)
        else:
            absolute = []
            for delta, weight in terms:
                value = model.addVar(lb=0)
                model.addConstr(value >= delta)
                model.addConstr(value >= -delta)
                absolute.append(weight * value)
            objective = gp.quicksum(absolute)
        model.setObjective(objective, gp.GRB.MINIMIZE)
        optimize(model)
        if model.Status != gp.GRB.OPTIMAL:
            raise RuntimeError(f"coordinate optimization failed: status={model.Status}")
        return {node: (initial[node][0], float(y[node].X)) for node in initial}
