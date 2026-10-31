"""通常の左から右へ進む階層図を Matplotlib で描画する。"""

from collections.abc import Hashable, Mapping, Sequence
from typing import TypeAlias

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import FancyArrowPatch

Node: TypeAlias = Hashable
Edge: TypeAlias = tuple[Node, Node]
Point: TypeAlias = tuple[float, float]


def draw_hierarchical_graph(
    nodes: Sequence[Node],
    original_edges: Sequence[Edge],
    positions: Mapping[Node, Point],
    chains: Mapping[Edge, Sequence[Node]],
    reversed_edges: frozenset[Edge],
) -> None:
    """画像を保存せず、Matplotlibで描画結果を表示する。

    頂点の大きさ、色、ラベル、矢印の形式、余白、動的な図の大きさは、意図的に
    ``src/drawing/draw_torus.py`` に合わせている。
    """
    figure = create_hierarchical_figure(
        nodes,
        original_edges,
        positions,
        chains,
        reversed_edges,
    )
    plt.show()
    plt.close(figure)


def create_hierarchical_figure(
    nodes: Sequence[Node],
    original_edges: Sequence[Edge],
    positions: Mapping[Node, Point],
    chains: Mapping[Edge, Sequence[Node]],
    reversed_edges: frozenset[Edge],
    *,
    figsize: tuple[float, float] | None = None,
):
    """杉山法による図を作成し、表示も終了処理もせずに返す。

    比較UIに図を埋め込む場合や、呼び出し側で保存する場合に利用できる。
    ``draw_hierarchical_graph`` は、単独で手軽に表示するためのAPIとして残す。
    """

    layer_coordinates = sorted({positions[node][0] for node in positions})
    node_counts_by_layer = [
        sum(positions[node][0] == coordinate for node in nodes)
        for coordinate in layer_coordinates
    ]
    num_layers = len(layer_coordinates)
    max_layer_size = max(node_counts_by_layer, default=1)
    width = max(1, num_layers + 1)
    height = max(1, max_layer_size + 1)
    if figsize is None:
        figsize = (width * 2, height * 2)
    figure, axis = plt.subplots(figsize=figsize)

    for original_edge in original_edges:
        source, target = original_edge
        layout_edge = (
            (target, source) if original_edge in reversed_edges else original_edge
        )
        path = list(chains[layout_edge])
        if original_edge in reversed_edges:
            path.reverse()
        _draw_path(
            axis,
            [positions[node] for node in path],
            reversed_edge=original_edge in reversed_edges,
        )

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=nodes,
        ax=axis,
        node_size=400,
        node_color="lightblue",
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels={node: node for node in nodes},
        ax=axis,
        font_size=10,
    )

    all_points = list(positions.values())
    xs = [point[0] for point in all_points]
    ys = [point[1] for point in all_points]
    x_margin = 0.55
    y_margin = 0.65
    axis.set_xlim(min(xs, default=0.0) - x_margin, max(xs, default=0.0) + x_margin)
    axis.set_ylim(min(ys, default=0.0) - y_margin, max(ys, default=0.0) + y_margin)
    axis.invert_yaxis()
    axis.axis("off")

    plt.tight_layout()
    return figure


def _draw_path(axis, points: Sequence[Point], reversed_edge: bool) -> None:
    """非表示のダミー折れ曲がり点を経由して、元の辺を1本描画する。"""

    color = "red" if reversed_edge else "black"
    line_style = "--" if reversed_edge else "-"
    node_radius = 0.15
    for index, (start, end) in enumerate(zip(points, points[1:])):
        is_last = index == len(points) - 2
        arrow = FancyArrowPatch(
            start,
            end,
            arrowstyle="->" if is_last else "-",
            mutation_scale=20,
            linestyle=line_style,
            color=color,
            shrinkA=node_radius * 100 if index == 0 else 0,
            shrinkB=node_radius * 100 if is_last else 0,
            zorder=1,
        )
        axis.add_patch(arrow)
