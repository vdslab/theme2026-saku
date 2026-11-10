"""Assign polar and Cartesian coordinates to a radial hierarchy."""

from . import constants

from dataclasses import dataclass
import math
from typing import Hashable, Iterable, TypeAlias

Node: TypeAlias = Hashable
Point: TypeAlias = tuple[float, float]
PolarPoint: TypeAlias = tuple[float, float]


@dataclass(frozen=True)
class RadialCoordinates:
    cartesian: dict[Node, Point]
    polar: dict[Node, PolarPoint]
    radii: dict[int, float]


def assign_coordinates(
    layers: dict[int, Iterable[Node]],
    *,
    inner_radius: float = constants.DEFAULT_INNER_RADIUS,
    layer_gap: float = constants.DEFAULT_LAYER_GAP,
    start_angle: float = constants.DEFAULT_START_ANGLE,
) -> RadialCoordinates:
    """Place each layer at equal angular intervals on a concentric circle."""

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

