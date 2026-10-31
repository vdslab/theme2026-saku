"""Figureを作成して返す。呼び出し側がcloseする。"""

from os import PathLike
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from ..models import SubdividedGraph, CrossingResult, CoordinateResult
from .models import DrawingOptions
from .preparation import prepare_drawing
from .geometry import paper_figure_size
from .artists import draw_edges, draw_nodes, draw_legend


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
    if show_layer_labels and (not tile_surroundings):
        ax.set_xticks(range(num_layers))
        ax.set_xticklabels(
            [f"L{layer}" for layer in sorted_layers], fontsize=max(6, font_size - 1)
        )
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
    draw_edges(ax, data, options)
    draw_nodes(ax, data, options)
    draw_legend(ax, data, options)
    ax.invert_yaxis()
    return fig
