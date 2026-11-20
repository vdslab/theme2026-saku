"""Experimental finite 3x3 cover: ordinary BK, then extract the central tile.

Replicas are independent during BK. This is deliberately a finite-cover
experiment, not a periodic-constrained version of the BK algorithm.
"""

from dataclasses import dataclass

from ..models import (
    CoordinateResult, CrossingResult, Graph, Node, Positions, SubdividedGraph,
)
from .periodic import center_in_period, drawing_period
from .preparation import complete_order, validate_graph
from .brandes_koepf import (
    align_to_narrowest, balanced_coordinates, map_node_layers, orient_order,
    single_bk_assignment,
)

type Replica = tuple[Node, int, int]


@dataclass(frozen=True)
class ExpandedGraph:
    graph: SubdividedGraph
    crossing: CrossingResult
    node_ids: dict[Replica, int]
    omitted_segments: int


def expand_3x3(graph: SubdividedGraph, crossing: CrossingResult) -> ExpandedGraph:
    """Lift edges to the copies selected by their fixed winding numbers.

    Edges leaving the nine tiles are omitted, never reconnected to the outer
    boundary. Node IDs are allocated independently of the input ID type.
    """
    order = complete_order(crossing.order, graph.layers, sorted(graph.layers))
    validate_graph(order, list(graph.graph.edges), crossing.winding_numbers)
    layer_count = len(order)
    node_ids: dict[Replica, int] = {}
    layers: dict[int, list[int]] = {}
    for horizontal in (-1, 0, 1):
        for index, nodes in enumerate(order.values()):
            expanded_nodes = []
            for vertical in (-1, 0, 1):
                for node in nodes:
                    replica = (node, horizontal, vertical)
                    node_ids[replica] = len(node_ids)
                    expanded_nodes.append(node_ids[replica])
            layers[(horizontal + 1) * layer_count + index] = expanded_nodes

    edges = []
    weights = {}
    omitted = 0
    for u, v in graph.graph.edges:
        winding = crossing.winding_numbers.get((u, v), 0)
        if winding != int(winding):
            raise ValueError("3x3 BK requires integer winding numbers")
        horizontal_step = int(graph.torus_flags.get((u, v), False))
        for horizontal in (-1, 0, 1):
            for vertical in (-1, 0, 1):
                target = (v, horizontal + horizontal_step, vertical + int(winding))
                if target not in node_ids:
                    omitted += 1
                    continue
                edge = (node_ids[u, horizontal, vertical], node_ids[target])
                edges.append(edge)
                weights[edge] = graph.weights.get((u, v), 1.0)
    originals = set(graph.original_nodes)
    expanded = SubdividedGraph(
        Graph(tuple(node_ids.values()), tuple(edges)), layers, {}, weights,
        tuple(replica_id for (node, _, _), replica_id in node_ids.items()
              if node in originals),
    )
    return ExpandedGraph(expanded, CrossingResult(layers, {}), node_ids, omitted)


def compute_replica_positions(
    expanded: ExpandedGraph, *, min_gap: float = 1.0,
) -> Positions:
    return compute_unprojected_coordinates(
        expanded.graph, expanded.crossing, min_gap=min_gap,
    ).positions


def compute_unprojected_coordinates(
    graph: SubdividedGraph, crossing: CrossingResult, *, min_gap: float,
) -> CoordinateResult:
    """Four BK assignments only; never project or smooth the result."""
    order = complete_order(crossing.order, graph.layers, sorted(graph.layers))
    validate_graph(order, list(graph.graph.edges), crossing.winding_numbers)
    layers = sorted(order)
    layer_index = {layer: index for index, layer in enumerate(layers)}
    node_to_layer = map_node_layers(order)
    variants = []
    directions = []
    for scan_forward in (True, False):
        for horizontal_forward in (True, False):
            values = single_bk_assignment(
                node_order=orient_order(order, horizontal_forward),
                edges=list(graph.graph.edges), t_val=graph.torus_flags,
                psi=crossing.winding_numbers, layers=layers,
                node_to_layer=node_to_layer, layer_index=layer_index,
                scan_forward=scan_forward, min_gap=min_gap,
                dummy_nodes=graph.dummy_nodes,
            )
            if not horizontal_forward:
                values = {node: -value for node, value in values.items()}
            variants.append(values)
            directions.append(horizontal_forward)
    y_values = balanced_coordinates(align_to_narrowest(variants, directions))
    return fit_coordinates(graph, y_values, min_gap=min_gap)


def fit_coordinates(
    graph: SubdividedGraph, y_values: dict[Node, float], *, min_gap: float,
) -> CoordinateResult:
    """Fit the drawing domain using only a common translation of the layout."""
    span = max(y_values.values(), default=0.0) - min(y_values.values(), default=0.0)
    period = max(drawing_period(graph.layers, min_gap), span + min_gap)
    max_size = max(1, max(map(len, graph.layers.values()), default=0))
    y_values = center_in_period(y_values, period, period / max_size)
    x_by_node = {
        node: float(index)
        for index, layer in enumerate(sorted(graph.layers))
        for node in graph.layers[layer]
    }
    return CoordinateResult(
        {node: (x_by_node[node], y) for node, y in y_values.items()}, period,
    )


def assign_replicated_coordinates(
    graph: SubdividedGraph, crossing: CrossingResult, *, min_gap: float,
) -> CoordinateResult:
    expanded = expand_3x3(graph, crossing)
    replicas = compute_replica_positions(expanded, min_gap=min_gap)
    if not replicas:
        return CoordinateResult({}, drawing_period(graph.layers, min_gap))
    central_y = {
        node: replicas[replica_id][1]
        for (node, horizontal, vertical), replica_id in expanded.node_ids.items()
        if horizontal == vertical == 0
    }
    return fit_coordinates(graph, central_y, min_gap=min_gap)
