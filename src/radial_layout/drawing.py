"""Matplotlib rendering for a concentric radial hierarchy."""

from . import constants

from collections.abc import Hashable, Mapping, Sequence
from itertools import combinations
import math
from pathlib import Path
from typing import TypeAlias

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Circle, ConnectionStyle, FancyArrowPatch
from matplotlib.path import Path as PlotPath

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]
Point: TypeAlias = tuple[float, float]
PolarPoint: TypeAlias = tuple[float, float]


def draw_radial_graph(
    nodes: Sequence[Node],
    original_edges: Sequence[Edge],
    positions: Mapping[Node, Point],
    polar_positions: Mapping[Node, PolarPoint],
    radii: Mapping[int, float],
    chains: Mapping[Edge, Sequence[Node]],
    winding: Mapping[Edge, int],
    reversed_edges: frozenset[Edge],
    *,
    save_path: str | Path | None = None,
    show: bool = constants.DEFAULT_SHOW_DRAWING,
) -> None:
    """Render the radial drawing, optionally save it, and close the figure."""

    figure = create_radial_figure(
        nodes,
        original_edges,
        positions,
        polar_positions,
        radii,
        chains,
        winding,
        reversed_edges,
    )
    if save_path is not None:
        output = Path(save_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=constants.DPI, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(figure)


def create_radial_figure(
    nodes: Sequence[Node],
    original_edges: Sequence[Edge],
    positions: Mapping[Node, Point],
    polar_positions: Mapping[Node, PolarPoint],
    radii: Mapping[int, float],
    chains: Mapping[Edge, Sequence[Node]],
    winding: Mapping[Edge, int],
    reversed_edges: frozenset[Edge],
    *,
    figsize: tuple[float, float] | None = None,
):
    """Create a radial drawing without displaying or closing it."""

    outer_radius = max(radii.values(), default=1.0)
    limit = outer_radius + constants.DRAWING_MARGIN
    nearest = min(
        (math.dist(positions[u], positions[v]) for u, v in combinations(nodes, 2)),
        default=math.inf,
    )
    marker_clearance = (math.sqrt(constants.NODE_SIZE) + constants.NODE_EDGE_WIDTH) / 0.8
    if figsize is None:
        space_for_nodes = 2 * limit / nearest * marker_clearance / 72 if nearest else math.inf
        side = min(constants.FIGURE_MAX_SIDE,
                   max(constants.FIGURE_MIN_SIDE, outer_radius * constants.FIGURE_RADIUS_SCALE, space_for_nodes))
        figsize = (side, side)
    figure, axis = plt.subplots(figsize=figsize)
    axis.set_xlim(-limit, limit)
    axis.set_ylim(-limit, limit)
    axis.set_aspect("equal")
    axis.axis("off")
    figure.tight_layout()
    axis.apply_aspect()
    points_per_unit = (axis.get_window_extent().width / (2 * limit)) * 72 / figure.dpi
    marker_scale = min(1.0, nearest * points_per_unit / marker_clearance) if nearest else 1.0

    for radius in radii.values():
        if radius == 0:
            continue
        axis.add_patch(
            Circle(
                (0.0, 0.0),
                radius,
                fill=False,
                linewidth=constants.RING_WIDTH,
                linestyle=constants.RING_LINESTYLE,
                edgecolor=constants.RING_COLOR,
                zorder=0,
            )
        )

    steps_by_band = _sampling_steps(polar_positions, winding)
    for original_edge in original_edges:
        layout_edge = (
            (original_edge[1], original_edge[0])
            if original_edge in reversed_edges
            else original_edge
        )
        sampled = _sample_chain(chains[layout_edge], polar_positions, winding, steps_by_band)
        if original_edge in reversed_edges:
            sampled.reverse()
        _draw_sampled_edge(
            axis,
            sampled,
            reversed_edge=original_edge in reversed_edges,
            marker_scale=marker_scale,
        )

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=list(nodes),
        ax=axis,
        node_size=constants.NODE_SIZE * marker_scale**2,
        node_color=constants.NODE_COLOR,
        edgecolors=constants.NODE_EDGE_COLOR,
        linewidths=constants.NODE_EDGE_WIDTH * marker_scale,
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels={node: node for node in nodes},
        ax=axis,
        font_size=constants.FONT_SIZE * marker_scale,
    )

    return figure


def _sample_chain(
    chain: Sequence[Node],
    polar_positions: Mapping[Node, PolarPoint],
    winding: Mapping[Edge, int],
    steps_by_band: Mapping[tuple[float, float], int] | None = None,
) -> list[Point]:
    if steps_by_band is None:
        steps_by_band = _sampling_steps(
            polar_positions, {edge: winding[edge] for edge in zip(chain, chain[1:])}
        )
    sampled: list[Point] = []
    for segment_index, (source, target) in enumerate(zip(chain, chain[1:])):
        radius_start, angle_start = polar_positions[source]
        radius_end, angle_end = polar_positions[target]
        if radius_start == 0:
            angle_start = angle_end
            delta = 0.0
        else:
            delta = angle_end - angle_start + math.tau * winding[source, target]
        steps = steps_by_band[radius_start, radius_end] if abs(delta) > 1e-12 else 1
        for step in range(int(segment_index > 0), steps):
            ratio = step / steps
            radius = radius_start + ratio * (radius_end - radius_start)
            angle = angle_start + ratio * delta
            sampled.append((radius * math.cos(angle), radius * math.sin(angle)))
        # Use the original polar endpoint so adjoining segments meet exactly.
        sampled.append((radius_end * math.cos(angle_end), radius_end * math.sin(angle_end)))
    return sampled


def _sampling_steps(polar_positions, winding):
    steps_by_band = {}
    for (u, v), offset in winding.items():
        inner, start = polar_positions[u]
        outer, end = polar_positions[v]
        span = abs(end - start + math.tau * offset) if inner else 0.0
        radial_level = outer / (outer - inner)
        # Eq. (5), plus a sufficient bound for every chord to move strictly
        # outward: r_next * cos(span / steps) > r_previous.
        steps = max(1, math.ceil(radial_level * span / math.tau * constants.CURVE_SAMPLES_PER_TURN),
                    math.ceil(span / constants.CURVE_MAX_ANGLE_STEP),
                    math.floor(radial_level * span**2 / 2) + 1)
        band = inner, outer
        steps_by_band[band] = max(steps_by_band.get(band, 1), steps)
    return steps_by_band


class _EdgeEnd(ConnectionStyle.Arc3):
    """Follow the sampled centerline into the arrowhead."""

    def __init__(self, axis, points, marker_scale):
        super().__init__()
        self.axis = axis
        self.points = points
        self.marker_scale = marker_scale

    def connect(self, posA, posB):
        distance = (2 * (constants.ARROW_SHRINK + constants.ARROW_SCALE)
                    * self.marker_scale * self.axis.figure.dpi / 72)
        transform = self.axis.transData
        for index in range(len(self.points) - 2, 0, -1):
            if math.dist(transform.transform(self.points[index]), posB) >= distance:
                break
        else:
            index = 0
        ends = transform.transform(self.points[index:])
        return PlotPath(ends, [PlotPath.MOVETO] + [PlotPath.LINETO] * (len(ends) - 1))


def _draw_sampled_edge(axis, points: Sequence[Point], *, reversed_edge: bool, marker_scale: float) -> None:
    if len(points) < 2:
        return
    color = constants.REVERSED_EDGE_COLOR if reversed_edge else constants.EDGE_COLOR
    linestyle = constants.REVERSED_EDGE_LINESTYLE if reversed_edge else constants.EDGE_LINESTYLE
    xs, ys = zip(*points)
    line, = axis.plot(xs, ys, color=color, linestyle=linestyle, linewidth=constants.EDGE_WIDTH, zorder=1)
    line.get_path().should_simplify = False
    axis.add_patch(
        FancyArrowPatch(
            points[0],
            points[-1],
            connectionstyle=_EdgeEnd(axis, points, marker_scale),
            arrowstyle="-|>",
            mutation_scale=constants.ARROW_SCALE * marker_scale,
            color=color,
            linewidth=0,
            shrinkA=0,
            shrinkB=constants.ARROW_SHRINK * marker_scale,
            zorder=2,
        )
    )

