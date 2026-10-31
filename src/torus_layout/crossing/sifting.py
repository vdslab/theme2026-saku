"""局所siftingと全体の最良状態の保持。"""

from ..models import Node, Edge, Layers, Winding
from .lib.types import OrientedEdge
from .lib.embedding import copy_order, forward_layer_pairs, oriented_pair_embedding
from .lib.crossings import (
    count_all_crossings,
    crossings_between_edge_sets,
    crossings_for_edge,
    crossings_involving_edges,
    pair_crossings,
    sifting_edge_weights,
)


def run_sifting_with_global_guard(
    order: Layers,
    psi: Winding,
    layers: list[int],
    edges: list[Edge],
    rounds: int,
    dummy_nodes: set[Node] | None = None,
    optimize_winding: bool = True,
) -> None:
    """Run the same local passes as ``_run_sifting`` and retain global best."""
    best_order = copy_order(order)
    best_psi = dict(psi)
    best_crossings = count_all_crossings(order, psi, layers, edges)
    layer_pairs = forward_layer_pairs(layers)
    two_pass_pairs = layer_pairs + layer_pairs[:-1]
    for fixed_layer, free_layer in two_pass_pairs:
        for _ in range(rounds):
            sift_two_layer_pair(
                fixed_layer,
                free_layer,
                order,
                psi,
                edges,
                dummy_nodes=dummy_nodes,
                optimize_winding=optimize_winding,
            )
            crossings = count_all_crossings(order, psi, layers, edges)
            if crossings < best_crossings:
                best_crossings = crossings
                best_order = copy_order(order)
                best_psi = dict(psi)
    order.clear()
    order.update(best_order)
    psi.clear()
    psi.update(best_psi)


def sift_two_layer_pair(
    fixed_layer: int,
    free_layer: int,
    order: Layers,
    psi: Winding,
    edges: list[Edge],
    dummy_nodes: set[Node] | None = None,
    optimize_winding: bool = True,
) -> None:
    """fixed_layerを固定し、free_layerだけを交差数でsiftingする。"""
    pair_edges, oriented_psi, original_edges = oriented_pair_embedding(
        order, psi, fixed_layer, free_layer, edges
    )
    if not pair_edges:
        return
    edge_weights = sifting_edge_weights(pair_edges, dummy_nodes, len(pair_edges))
    current_crossings = pair_crossings(
        order,
        oriented_psi,
        fixed_layer,
        free_layer,
        pair_edges,
        edge_weights=edge_weights,
    )
    for node in list(order[free_layer]):
        incident_edges = [edge for edge in pair_edges if edge[1] == node]
        if incident_edges:
            if optimize_winding:
                current_crossings = sift_vertex_one_sided(
                    node,
                    fixed_layer,
                    free_layer,
                    order,
                    oriented_psi,
                    pair_edges,
                    incident_edges,
                    current_crossings,
                    edge_weights,
                )
            else:
                current_crossings = sift_vertex_with_fixed_winding(
                    node,
                    fixed_layer,
                    free_layer,
                    order,
                    oriented_psi,
                    pair_edges,
                    incident_edges,
                    current_crossings,
                    edge_weights,
                )
    for oriented_edge, (original_edge, direction) in original_edges.items():
        psi[original_edge] = direction * oriented_psi[oriented_edge]


def sift_vertex_with_fixed_winding(
    node: Node,
    fixed_layer: int,
    free_layer: int,
    order: Layers,
    psi: dict[OrientedEdge, int],
    pair_edges: list[OrientedEdge],
    incident_edges: list[OrientedEdge],
    current_crossings: int,
    edge_weights: dict[OrientedEdge, int],
) -> int:
    """psiを固定し、自由層内の頂点位置だけを全候補から選ぶ。"""
    free_nodes = order[free_layer]
    if len(free_nodes) <= 1:
        return current_crossings
    best_crossings = current_crossings
    best_nodes = list(free_nodes)
    original_incident_crossings = crossings_involving_edges(
        incident_edges, pair_edges, order, psi, fixed_layer, free_layer, edge_weights
    )
    unaffected_crossings = current_crossings - original_incident_crossings
    remaining = [candidate for candidate in free_nodes if candidate != node]
    for position in range(len(free_nodes)):
        candidate_nodes = list(remaining)
        candidate_nodes.insert(position, node)
        order[free_layer] = candidate_nodes
        candidate_crossings = unaffected_crossings + crossings_involving_edges(
            incident_edges,
            pair_edges,
            order,
            psi,
            fixed_layer,
            free_layer,
            edge_weights,
        )
        if candidate_crossings < best_crossings:
            best_crossings = candidate_crossings
            best_nodes = candidate_nodes
    order[free_layer] = best_nodes
    return best_crossings


def sift_vertex_one_sided(
    node: Node,
    fixed_layer: int,
    free_layer: int,
    order: Layers,
    psi: dict[OrientedEdge, int],
    pair_edges: list[OrientedEdge],
    incident_edges: list[OrientedEdge],
    current_crossings: int,
    edge_weights: dict[OrientedEdge, int],
) -> int:
    """論文のparting探索を使い、2層間の交差数だけで1頂点をsiftingする。"""
    free_nodes = order[free_layer]
    if len(free_nodes) <= 1:
        return current_crossings
    fixed_position = {
        fixed_node: index for index, fixed_node in enumerate(order[fixed_layer])
    }
    sorted_incident = sorted(incident_edges, key=lambda edge: fixed_position[edge[0]])
    best_crossings = current_crossings
    best_nodes = list(free_nodes)
    best_offsets = {edge: psi.get(edge, 0) for edge in sorted_incident}
    original_incident_crossings = crossings_involving_edges(
        sorted_incident, pair_edges, order, psi, fixed_layer, free_layer, edge_weights
    )
    working_order = copy_order(order)
    working_psi = dict(psi)
    working_nodes = working_order[free_layer]
    working_nodes.remove(node)
    working_nodes.insert(0, node)
    for edge in sorted_incident:
        working_psi[edge] = 1
    current_crossings = (
        best_crossings
        - original_incident_crossings
        + crossings_involving_edges(
            sorted_incident,
            pair_edges,
            working_order,
            working_psi,
            fixed_layer,
            free_layer,
            edge_weights,
        )
    )
    offset = 0
    parting = 0
    for position in range(len(working_nodes) - 1):
        offset, parting, current_crossings = advance_parting(
            sorted_incident,
            offset,
            parting,
            current_crossings,
            working_order,
            working_psi,
            pair_edges,
            fixed_layer,
            free_layer,
            edge_weights,
        )
        if current_crossings < best_crossings:
            best_crossings = current_crossings
            best_nodes = list(working_order[free_layer])
            best_offsets = {edge: working_psi[edge] for edge in sorted_incident}
        if position < len(working_nodes) - 2:
            node_index = working_order[free_layer].index(node)
            next_node = working_order[free_layer][node_index + 1]
            next_incident = [edge for edge in pair_edges if edge[1] == next_node]
            before_swap = crossings_between_edge_sets(
                sorted_incident,
                next_incident,
                working_order,
                working_psi,
                fixed_layer,
                free_layer,
                edge_weights,
            )
            (
                working_order[free_layer][node_index],
                working_order[free_layer][node_index + 1],
            ) = (
                working_order[free_layer][node_index + 1],
                working_order[free_layer][node_index],
            )
            after_swap = crossings_between_edge_sets(
                sorted_incident,
                next_incident,
                working_order,
                working_psi,
                fixed_layer,
                free_layer,
                edge_weights,
            )
            current_crossings += after_swap - before_swap
    order[free_layer] = best_nodes
    for edge, value in best_offsets.items():
        psi[edge] = value
    return best_crossings


def advance_parting(
    incident_edges: list[OrientedEdge],
    offset: int,
    parting: int,
    current_crossings: int,
    order: Layers,
    psi: dict[OrientedEdge, int],
    pair_edges: list[OrientedEdge],
    fixed_layer: int,
    free_layer: int,
    edge_weights: dict[OrientedEdge, int],
) -> tuple[int, int, int]:
    """2層間の交差数を増やさない間、論文のpartingを進める。"""
    degree = len(incident_edges)
    while offset >= -1:
        edge = incident_edges[parting]
        before_crossings = crossings_for_edge(
            edge, pair_edges, order, psi, fixed_layer, free_layer, edge_weights
        )
        old_value = psi[edge]
        psi[edge] = offset
        after_crossings = crossings_for_edge(
            edge, pair_edges, order, psi, fixed_layer, free_layer, edge_weights
        )
        if after_crossings > before_crossings:
            psi[edge] = old_value
            break
        current_crossings += after_crossings - before_crossings
        parting += 1
        if parting == degree:
            offset -= 1
            parting = 0
    return (offset, parting, current_crossings)
