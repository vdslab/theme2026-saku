"""ノード・辺・凡例の描画。Figureの保存や表示は行わない。"""

import math
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from ..models import Node
from .styles import EDGE_STYLES, EdgeStyle
from .models import DrawingData, DrawingOptions
from .geometry import periodic_edge_segments

NODE_OUTLINE_WIDTH = 0.8
DUMMY_NODE_OUTLINE_WIDTH = 0.35


def add_edge_patch(
    ax: Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    style: EdgeStyle,
    edge_width: float,
    *,
    arrow: bool,
    shrink_a: float = 0.0,
    shrink_b: float = 0.0
) -> None:
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>" if arrow else "-",
        mutation_scale=9 if arrow else 1,
        shrinkA=shrink_a,
        shrinkB=shrink_b,
        color=style["color"],
        linestyle=style["linestyle"],
        linewidth=edge_width,
        alpha=0.86,
        capstyle="round",
        joinstyle="round",
        zorder=1,
        clip_on=False,
    )
    ax.add_patch(patch)


def legend_handle(style: EdgeStyle, edge_width: float) -> Line2D:
    return Line2D(
        [0],
        [0],
        color=style["color"],
        linestyle=style["linestyle"],
        linewidth=edge_width,
        label=style["label"],
    )


def draw_edges(ax: Axes, data: DrawingData, options: DrawingOptions) -> None:
    V = data.original_nodes
    pos = data.positions
    V_set = set(V)
    x_min = data.x_min
    x_max = data.x_max
    y_min = data.y_min
    y_max = data.y_max
    left_right_torus = data.left_right_torus
    positive_wrap_edges = data.positive_wrap_edges
    negative_wrap_edges = data.negative_wrap_edges
    horizontal_positive_wrap_edges = data.horizontal_positive_wrap_edges
    horizontal_negative_wrap_edges = data.horizontal_negative_wrap_edges
    normal_edges = data.normal_edges
    draw_dummy_nodes = options.draw_dummy_nodes
    node_size = options.node_size
    dummy_node_size = options.dummy_node_size
    edge_width = options.edge_width

    def node_shrink(node: Node) -> float:
        if node not in V_set and (not draw_dummy_nodes):
            return 0.0
        size = node_size if node in V_set else dummy_node_size
        return math.sqrt(size / math.pi) + 0.8

    def edge_has_arrow(target: Node) -> bool:
        return draw_dummy_nodes or target in V_set

    def draw_periodic_edge(u: Node, v: Node, style: EdgeStyle, horizontal: int) -> None:
        # Keep the full winding: a seam change can produce |psi| > 1.
        segments = periodic_edge_segments(
            pos[u], pos[v],
            x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max,
            horizontal_winding=horizontal,
            vertical_winding=data.winding_numbers.get((u, v), 0),
        )
        for index, (start, end) in enumerate(segments):
            add_edge_patch(
                ax, start, end, style, edge_width,
                arrow=index == len(segments) - 1 and edge_has_arrow(v),
                shrink_a=node_shrink(u) if index == 0 else 0.0,
                shrink_b=node_shrink(v) if index == len(segments) - 1 else 0.0,
            )

    for u, v in normal_edges:
        add_edge_patch(
            ax,
            pos[u],
            pos[v],
            EDGE_STYLES["normal"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_a=node_shrink(u),
            shrink_b=node_shrink(v),
        )
    for u, v in left_right_torus:
        u_pos = pos[u]
        v_pos = pos[v]
        dist_to_right = x_max - u_pos[0]
        dist_from_left = v_pos[0] - x_min
        total_x_dist = dist_to_right + dist_from_left
        slope = (v_pos[1] - u_pos[1]) / total_x_dist
        boundary_y = u_pos[1] + slope * dist_to_right
        add_edge_patch(
            ax,
            u_pos,
            (x_max, boundary_y),
            EDGE_STYLES["horizontal_wrap"],
            edge_width,
            arrow=False,
            shrink_a=node_shrink(u),
        )
        add_edge_patch(
            ax,
            (x_min, boundary_y),
            v_pos,
            EDGE_STYLES["horizontal_wrap"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_b=node_shrink(v),
        )
    combined_wrap_groups = (
        (horizontal_positive_wrap_edges, 1, EDGE_STYLES["horizontal_positive_wrap"]),
        (horizontal_negative_wrap_edges, -1, EDGE_STYLES["horizontal_negative_wrap"]),
    )
    for edges, _vertical_sign, style in combined_wrap_groups:
        for u, v in edges:
            draw_periodic_edge(u, v, style, horizontal=1)
    for u, v in positive_wrap_edges:
        if data.winding_numbers[u, v] > 1:
            draw_periodic_edge(u, v, EDGE_STYLES["positive_wrap"], horizontal=0)
            continue
        u_pos = pos[u]
        v_pos = pos[v]
        dist_to_top = y_max - u_pos[1]
        dist_from_bottom = v_pos[1] - y_min
        total_y_dist = dist_to_top + dist_from_bottom
        slope = (v_pos[0] - u_pos[0]) / total_y_dist
        boundary_x = u_pos[0] + slope * dist_to_top
        add_edge_patch(
            ax,
            u_pos,
            (boundary_x, y_max),
            EDGE_STYLES["positive_wrap"],
            edge_width,
            arrow=False,
            shrink_a=node_shrink(u),
        )
        add_edge_patch(
            ax,
            (boundary_x, y_min),
            v_pos,
            EDGE_STYLES["positive_wrap"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_b=node_shrink(v),
        )
    for u, v in negative_wrap_edges:
        if data.winding_numbers[u, v] < -1:
            draw_periodic_edge(u, v, EDGE_STYLES["negative_wrap"], horizontal=0)
            continue
        u_pos = pos[u]
        v_pos = pos[v]
        dist_to_bottom = u_pos[1] - y_min
        dist_from_top = y_max - v_pos[1]
        total_y_dist = dist_to_bottom + dist_from_top
        slope = (v_pos[0] - u_pos[0]) / total_y_dist
        boundary_x = u_pos[0] + slope * dist_to_bottom
        add_edge_patch(
            ax,
            u_pos,
            (boundary_x, y_min),
            EDGE_STYLES["negative_wrap"],
            edge_width,
            arrow=False,
            shrink_a=node_shrink(u),
        )
        add_edge_patch(
            ax,
            (boundary_x, y_max),
            v_pos,
            EDGE_STYLES["negative_wrap"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_b=node_shrink(v),
        )


def draw_nodes(ax: Axes, data: DrawingData, options: DrawingOptions) -> None:
    V = data.original_nodes
    pos = data.positions
    dummy_nodes = data.dummy_nodes
    draw_dummy_nodes = options.draw_dummy_nodes
    node_size = options.node_size
    dummy_node_size = options.dummy_node_size
    font_size = options.font_size
    visible_nodes = [node for node in V if node in pos]
    if visible_nodes:
        xs = [pos[node][0] for node in visible_nodes]
        ys = [pos[node][1] for node in visible_nodes]
        ax.scatter(
            xs,
            ys,
            s=node_size,
            c="#F2F7FA",
            edgecolors="#1A1A1A",
            linewidths=NODE_OUTLINE_WIDTH,
            zorder=3,
            marker="o",
        )
        for node in visible_nodes:
            ax.text(
                pos[node][0],
                pos[node][1],
                str(node),
                ha="center",
                va="center",
                fontsize=font_size,
                color="#111111",
                zorder=4,
            )
    if draw_dummy_nodes and dummy_nodes:
        xs = [pos[node][0] for node in dummy_nodes]
        ys = [pos[node][1] for node in dummy_nodes]
        ax.scatter(
            xs,
            ys,
            s=dummy_node_size,
            c="#777777",
            edgecolors="white",
            linewidths=DUMMY_NODE_OUTLINE_WIDTH,
            marker="o",
            zorder=3,
        )


def draw_legend(ax: Axes, data: DrawingData, options: DrawingOptions) -> None:
    dummy_nodes = data.dummy_nodes
    left_right_torus = data.left_right_torus
    positive_wrap_edges = data.positive_wrap_edges
    negative_wrap_edges = data.negative_wrap_edges
    horizontal_positive_wrap_edges = data.horizontal_positive_wrap_edges
    horizontal_negative_wrap_edges = data.horizontal_negative_wrap_edges
    normal_edges = data.normal_edges
    draw_dummy_nodes = options.draw_dummy_nodes
    dummy_node_size = options.dummy_node_size
    font_size = options.font_size
    edge_width = options.edge_width
    show_legend = options.show_legend
    tile_surroundings = options.tile_surroundings
    if show_legend and (not tile_surroundings):
        present_styles: list[str] = []
        if normal_edges:
            present_styles.append("normal")
        if left_right_torus:
            present_styles.append("horizontal_wrap")
        if positive_wrap_edges:
            present_styles.append("positive_wrap")
        if negative_wrap_edges:
            present_styles.append("negative_wrap")
        if horizontal_positive_wrap_edges:
            present_styles.append("horizontal_positive_wrap")
        if horizontal_negative_wrap_edges:
            present_styles.append("horizontal_negative_wrap")
        handles: list[Line2D] = []
        for key in present_styles:
            style = EDGE_STYLES[key]
            # The shared color indicates the sign, not necessarily one turn.
            if any(abs(value) > 1 for value in data.winding_numbers.values()):
                style = {
                    **style,
                    "label": style["label"].replace("\\psi=+1", "\\psi>0").replace("\\psi=-1", "\\psi<0"),
                }
            handles.append(legend_handle(style, edge_width))
        if draw_dummy_nodes and dummy_nodes:
            handles.append(
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markerfacecolor="#777777",
                    markeredgecolor="white",
                    markersize=max(3.5, math.sqrt(dummy_node_size)),
                    label="Dummy node",
                )
            )
        if handles:
            ax.legend(
                handles=handles,
                loc="lower center",
                bbox_to_anchor=(0.5, 1.01),
                ncol=min(2, len(handles)),
                frameon=False,
                fontsize=max(6, font_size - 1),
                handlelength=2.8,
                columnspacing=1.2,
            )
