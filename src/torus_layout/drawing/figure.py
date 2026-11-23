"""Figureを作成して返す。呼び出し側がcloseする。"""

from dataclasses import replace
from math import sqrt
from os import PathLike
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from ..models import SubdividedGraph, CrossingResult, CoordinateResult
from .models import DrawingData, DrawingOptions
from .preparation import prepare_drawing
from .geometry import fit_marker_margins, paper_figure_size
from .artists import (
    DUMMY_NODE_OUTLINE_WIDTH, NODE_OUTLINE_WIDTH, draw_edges, draw_nodes, draw_legend,
)


def _inset_nodes(
    fig: Figure, ax: Axes, data: DrawingData, options: DrawingOptions,
) -> tuple[DrawingData, float, float]:
    # Scatter sizes are in points squared. Include half the outline and the
    # border painted over the raster tile, with room for crop rounding.
    border = 2 * 72 / options.dpi if options.tile_surroundings else 0.35
    groups = [
        (data.original_nodes, (sqrt(options.node_size) + NODE_OUTLINE_WIDTH) / 2 + border),
        (data.dummy_nodes, (sqrt(options.dummy_node_size) + DUMMY_NODE_OUTLINE_WIDTH) / 2
         + border if options.draw_dummy_nodes else 0.0),
    ]
    groups = [([node for node in nodes if node in data.positions], radius)
              for nodes, radius in groups]
    groups = [(nodes, radius) for nodes, radius in groups if nodes]
    if not groups or not any(radius for _, radius in groups):
        return data, 1.0, 0.0
    original_position = ax.get_position(original=True).frozen()
    fig.canvas.draw()
    axes_inches = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    # Reserve enough physical room even for oversized markers or tiny figures.
    required_inches = 2 * max(radius for _, radius in groups) / 72
    if required_inches >= min(axes_inches.width, axes_inches.height):
        factor = 1 + required_inches / min(axes_inches.width, axes_inches.height)
        fig.set_size_inches(fig.get_figwidth() * factor, fig.get_figheight() * factor)
        fig.canvas.draw()
        axes_inches = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())

    transforms = []
    for axis, lower, upper, inches in (
        (0, data.x_min, data.x_max, axes_inches.width),
        (1, data.y_min, data.y_max, axes_inches.height),
    ):
        ranges = []
        for nodes, radius in groups:
            centers = [data.positions[node][axis] for node in nodes]
            margin = max(radius / (72 * inches), 1e-10) * (upper - lower)
            ranges.append((min(centers), max(centers), margin))
        transforms.append(fit_marker_margins(lower, upper, ranges))

    (x_scale, x_shift), (y_scale, y_shift) = transforms
    if transforms == [(1.0, 0.0), (1.0, 0.0)]:
        ax.set_position(original_position)
        ax.set_in_layout(True)
        return data, x_scale, x_shift
    # Keep the measured scale through saving and recompute the edge geometry
    # from the same inset positions, including all periodic boundary segments.
    fig.set_layout_engine(None)
    positions = {
        node: (x_scale * x + x_shift, y_scale * y + y_shift)
        for node, (x, y) in data.positions.items()
    }
    return replace(data, positions=positions), x_scale, x_shift


def create_figure(
    graph: SubdividedGraph,
    crossing: CrossingResult,
    coordinates: CoordinateResult | None = None,
    *,
    options: DrawingOptions | None = None,
    save_path: str | PathLike[str] | None = None,
) -> Figure:
    options = DrawingOptions() if options is None else options
    period = options.vertical_period
    if period is None and coordinates is not None:
        period = coordinates.period
    data = prepare_drawing(
        list(graph.original_nodes),
        list(graph.graph.edges),
        graph.layers,
        order=crossing.order,
        psi=crossing.winding_numbers,
        t_val=graph.torus_flags,
        pos=None if coordinates is None else coordinates.positions,
        save_path=save_path,
        draw_dummy_nodes=options.draw_dummy_nodes,
        align_edges=options.align_edges,
        alignment_iterations=options.alignment_iterations,
        figsize=options.figsize,
        dpi=options.dpi,
        show_legend=options.show_legend,
        show_layer_labels=options.show_layer_labels,
        node_size=options.node_size,
        dummy_node_size=options.dummy_node_size,
        font_size=options.font_size,
        edge_width=options.edge_width,
        vertical_period=period,
        tile_surroundings=options.tile_surroundings,
        surrounding_opacity=options.surrounding_opacity,
        tile_gap=options.tile_gap,
    )
    figsize = options.figsize
    num_layers, max_layer_size = (data.num_layers, data.max_layer_size)
    sorted_layers = data.sorted_layers
    x_min, x_max, y_min, y_max = (data.x_min, data.x_max, data.y_min, data.y_max)
    show_legend, tile_surroundings = (options.show_legend, options.tile_surroundings)
    show_layer_labels, font_size = (options.show_layer_labels, options.font_size)
    if figsize is None:
        figsize = paper_figure_size(
            num_layers, max_layer_size, show_legend and (not tile_surroundings)
        )
    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)
    ax.set_facecolor("white")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_yticks([])
    show_ticks = show_layer_labels and not tile_surroundings
    layer_labels = [f"L{layer}" for layer in sorted_layers]
    if show_ticks:
        ax.set_xticks(range(num_layers))
        ax.set_xticklabels(layer_labels, fontsize=max(6, font_size - 1))
        ax.tick_params(axis="x", length=0, pad=3)
    else:
        ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if not tile_surroundings:
        ax.add_patch(
            Rectangle(
                (x_min, y_min),
                x_max - x_min,
                y_max - y_min,
                fill=False,
                edgecolor="#8A8A8A",
                linewidth=0.7,
                zorder=0,
                clip_on=False,
            )
        )
    draw_legend(ax, data, options)
    ax.invert_yaxis()
    data, x_scale, x_shift = _inset_nodes(fig, ax, data, options)
    if show_ticks and (x_scale, x_shift) != (1.0, 0.0):
        ax.set_xticks([x_scale * layer + x_shift for layer in range(num_layers)])
        ax.set_xticklabels(layer_labels, fontsize=max(6, font_size - 1))
        ax.set_xlim(x_min, x_max)
    draw_edges(ax, data, options)
    draw_nodes(ax, data, options)
    return fig
