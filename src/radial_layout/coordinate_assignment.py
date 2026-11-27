"""Assign polar and Cartesian coordinates to a radial hierarchy."""

from collections import defaultdict
from dataclasses import dataclass, field
import math
from statistics import median
from typing import Hashable, Iterable, TypeAlias

from layout_common.brandes_koepf import assign_within_layer_coordinates
from layout_common.hierarchy import DummyNode

from . import constants
from .crossing_reduction import RadialEmbedding, balance_level_rotation, count_crossings, rotate_level

Node: TypeAlias = Hashable
Point: TypeAlias = tuple[float, float]
PolarPoint: TypeAlias = tuple[float, float]


@dataclass(frozen=True)
class RadialCoordinates:
    cartesian: dict[Node, Point]
    polar: dict[Node, PolarPoint]
    radii: dict[int, float]
    winding: dict[tuple[Node, Node], int] = field(default_factory=dict)


def assign_coordinates(
    layers: dict[int, Iterable[Node]] | RadialEmbedding,
    *,
    inner_radius: float = constants.DEFAULT_INNER_RADIUS,
    layer_gap: float = constants.DEFAULT_LAYER_GAP,
    start_angle: float = constants.DEFAULT_START_ANGLE,
) -> RadialCoordinates:
    """Draw a Bachmaier embedding, or space an order-only input evenly.

    The embedding uses the radii specified in §5.4, scaled by layer_gap.
    inner_radius applies to the order-only input.
    """
    if isinstance(layers, RadialEmbedding):
        return _draw_embedding(layers, layer_gap, start_angle)

    if inner_radius <= 0 or layer_gap <= 0:
        raise ValueError("inner_radius and layer_gap must be positive")
    cartesian: dict[Node, Point] = {}
    polar: dict[Node, PolarPoint] = {}
    radii: dict[int, float] = {}
    for layer, nodes_iterable in sorted(layers.items()):
        nodes = tuple(nodes_iterable)
        radius = inner_radius + layer * layer_gap
        radii[layer] = radius
        for index, node in enumerate(nodes):
            angle = start_angle + 2 * math.pi * index / len(nodes)
            polar[node] = (radius, angle)
            cartesian[node] = (radius * math.cos(angle), radius * math.sin(angle))
    return RadialCoordinates(cartesian, polar, radii)


def _draw_embedding(embedding: RadialEmbedding, gap: float, start_angle: float) -> RadialCoordinates:
    """Unwind cut inner segments and transform the compacted strip (§5)."""
    if gap <= 0:
        raise ValueError("layer_gap must be positive")
    order = {level: list(nodes) for level, nodes in sorted(embedding.order.items())}
    winding = embedding.winding.copy()
    node_layers = {node: level for level, nodes in order.items() for node in nodes}
    dummies = {node for node in node_layers if isinstance(node, DummyNode)}
    if not node_layers:
        return RadialCoordinates({}, {}, {}, winding)
    boundaries = defaultdict(list)
    for edge in winding:
        boundaries[node_layers[edge[1]]].append(edge)
    inner_segments = tuple(edge for edge in winding if set(edge) <= dummies)
    if count_crossings(order, inner_segments, winding):
        raise ValueError("Bachmaier coordinate assignment requires no crossing inner segments")

    first = min(order)
    at_center = len(order[first]) == 1
    if at_center:
        for edge in boundaries[first + 1]:
            winding[edge] = 0

    for level, nodes in order.items():
        incoming = boundaries[level]
        inner = [edge for edge in incoming if set(edge) <= dummies]
        if not inner:
            # A ray rotation on the previous level changes this band as
            # well. Here there are no inner segments to constrain the ray.
            if incoming and not (at_center and level == first + 1):
                balance_level_rotation(order, winding, level, incoming, boundaries[level + 1])
            continue
        common = min(winding[edge] for edge in inner)
        for edge in incoming:
            winding[edge] -= common
        wraps = {edge[1] for edge in inner if winding[edge] == 1}
        if wraps:
            steps = max(i + 1 for i, node in enumerate(nodes) if node in wraps)
            rotate_level(order, winding, level, steps, incoming, boundaries[level + 1])

    radii = {
        level: gap * (level - first + (0 if at_center else 0.5)) for level in order
    }
    remaining = {level: nodes for level, nodes in order.items() if not (at_center and level == first)}
    separation = {level: gap / radii[level] for level in remaining}
    horizontal = assign_within_layer_coordinates(
        remaining,
        (edge for edge, offset in winding.items()
         if offset == 0 and (not at_center or node_layers[edge[0]] != first)),
        dummy_nodes=dummies.intersection(node for nodes in remaining.values() for node in nodes),
        separation=separation,
    )
    period = max(
        (max(horizontal[node] for node in nodes) - min(horizontal[node] for node in nodes)
         + separation[level] for level, nodes in remaining.items() if nodes),
        default=1.0,
    )
    origin = min(horizontal.values(), default=0.0)
    angles = {node: start_angle + math.tau * (horizontal.get(node, origin) - origin) / period
              for node in node_layers}
    aligned_levels = {node_layers[v] for _, v in inner_segments}
    phase = 0.0
    polar = {}
    for level, nodes in order.items():
        incoming = boundaries[level]
        if incoming and level not in aligned_levels and radii[level - 1] > 0:
            # In a band without an aligned dummy chain, rotate the entire
            # outer drawing by the median signed angle after compaction.
            # The common shift preserves intersection counts and minimizes
            # summed angular travel in this band.
            phase -= median(angles[v] - angles[u] + math.tau * winding[u, v]
                            for u, v in incoming)
        for node in nodes:
            polar[node] = radii[level], angles[node] + phase
    cartesian = {node: (radius * math.cos(angle), radius * math.sin(angle))
                 for node, (radius, angle) in polar.items()}
    return RadialCoordinates(cartesian, polar, radii, winding)
