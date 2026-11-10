"""Matplotlib rendering for a concentric radial hierarchy."""

from . import constants

from collections.abc import Hashable, Mapping, Sequence
import math
from pathlib import Path
from typing import TypeAlias

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Circle, FancyArrowPatch

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
    if figsize is None:
        side = max(constants.FIGURE_MIN_SIDE, min(constants.FIGURE_MAX_SIDE, outer_radius * constants.FIGURE_RADIUS_SCALE))
        figsize = (side, side)
    figure, axis = plt.subplots(figsize=figsize)
    for radius in radii.values():
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

    for original_edge in original_edges:
        layout_edge = (
            (original_edge[1], original_edge[0])
            if original_edge in reversed_edges
            else original_edge
        )
        path = list(chains[layout_edge])
        sampled = _sample_chain(path, polar_positions, winding)
        if original_edge in reversed_edges:
            sampled.reverse()
        _draw_sampled_edge(
            axis,
            sampled,
            reversed_edge=original_edge in reversed_edges,
        )

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=list(nodes),
        ax=axis,
        node_size=constants.NODE_SIZE,
        node_color=constants.NODE_COLOR,
        edgecolors=constants.NODE_EDGE_COLOR,
        linewidths=constants.NODE_EDGE_WIDTH,
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels={node: node for node in nodes},
        ax=axis,
        font_size=constants.FONT_SIZE,
    )

    margin = constants.DRAWING_MARGIN
    limit = outer_radius + margin
    axis.set_xlim(-limit, limit)
    axis.set_ylim(-limit, limit)
    axis.set_aspect("equal")
    axis.axis("off")
    figure.tight_layout()
    return figure


def _sample_chain(
    chain: Sequence[Node],
    polar_positions: Mapping[Node, PolarPoint],
    winding: Mapping[Edge, int],
) -> list[Point]:
    sampled: list[Point] = []
    for segment_index, (source, target) in enumerate(zip(chain, chain[1:])):
        radius_start, angle_start = polar_positions[source]
        radius_end, angle_end = polar_positions[target]
        angle_end += 2 * math.pi * winding[(source, target)]
        steps = constants.CURVE_SAMPLE_STEPS
        segment = []
        for step in range(steps + 1):
            ratio = step / steps
            radius = radius_start + ratio * (radius_end - radius_start)
            angle = angle_start + ratio * (angle_end - angle_start)
            segment.append((radius * math.cos(angle), radius * math.sin(angle)))
        sampled.extend(segment if segment_index == 0 else segment[1:])
    return sampled


def _draw_sampled_edge(axis, points: Sequence[Point], *, reversed_edge: bool) -> None:
    if len(points) < 2:
        return
    color = constants.REVERSED_EDGE_COLOR if reversed_edge else constants.EDGE_COLOR
    linestyle = constants.REVERSED_EDGE_LINESTYLE if reversed_edge else constants.EDGE_LINESTYLE
    xs, ys = zip(*points)
    axis.plot(xs, ys, color=color, linestyle=linestyle, linewidth=constants.EDGE_WIDTH, zorder=1)
    arrow_start_index = max(0, len(points) - 4)
    axis.add_patch(
        FancyArrowPatch(
            points[arrow_start_index],
            points[-1],
            arrowstyle="-|>",
            mutation_scale=constants.ARROW_SCALE,
            color=color,
            linewidth=constants.EDGE_WIDTH,
            shrinkA=0,
            shrinkB=constants.ARROW_SHRINK,
            zorder=2,
        )
    )

