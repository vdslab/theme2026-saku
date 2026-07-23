"""平坦トーラス（Radial Layout）の切開図を描画する関数。

通常の階層レイアウト + Radial Layoutの組み合わせ:
- 左右のトーラス: 最右レイヤーから最左レイヤーへの逆辺（既存実装と同じ）
- 上下のトーラス: ray（各レイヤーの上下境界）をまたぐエッジ（ψ≠0）
- 複合トーラス: 左右・上下の境界をともにまたぐエッジ（t=True かつ ψ≠0）
"""

from collections import defaultdict
from io import BytesIO
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle
from PIL import Image

from drawing.tile_image import (
    create_torus_context_image,
    validate_torus_context_options,
)

EDGE_STYLES = {
    "normal": {
        "color": "#333333",
        "linestyle": "-",
        "label": "Ordinary",
    },
    "horizontal_wrap": {
        "color": "#D55E00",
        "linestyle": (0, (5, 2)),
        "label": "Horizontal wrap",
    },
    "positive_wrap": {
        "color": "#0072B2",
        "linestyle": (0, (3, 1.5, 1, 1.5)),
        "label": r"$\psi=+1$: bottom-to-top",
    },
    "negative_wrap": {
        "color": "#CC79A7",
        "linestyle": (0, (1.5, 1.5)),
        "label": r"$\psi=-1$: top-to-bottom",
    },
    "horizontal_positive_wrap": {
        "color": "#009E73",
        "linestyle": (0, (5, 1.5, 1, 1.5)),
        "label": r"Horizontal + $\psi=+1$",
    },
    "horizontal_negative_wrap": {
        "color": "#882255",
        "linestyle": (0, (5, 1.5, 1, 1.5)),
        "label": r"Horizontal + $\psi=-1$",
    },
}


def draw_radial_torus(
    V,
    A,
    L,
    order=None,
    psi=None,
    t_val=None,
    pos=None,
    save_path=None,
    show=True,
    draw_dummy_nodes=False,
    align_edges=True,
    alignment_iterations=8,
    figsize=None,
    dpi=300,
    show_legend=True,
    show_layer_labels=True,
    node_size=260,
    dummy_node_size=28,
    font_size=8,
    edge_width=0.9,
    vertical_period=None,
    tile_surroundings=False,
    surrounding_opacity=0.8,
    tile_gap=0,
):
    """
    平坦トーラスグラフを描画（階層レイアウト + Radial境界）

    Args:
        V: ノード集合 list[int]
        A: エッジ集合 list[tuple(int, int)]
        L: レイヤー集合 dict[int: list[int]]
        order: 各階層内のノード順序 dict[layer: list[nodes]] (オプション)
        psi: 各エッジの巻き数 dict[(u,v): int] (オプション、-1/0/+1)
        t_val: 各エッジがトーラス辺か dict[(int,int): bool] (オプション、左右のトーラス用)
        pos: 各ノードの描画座標 dict[node: (x,y)] (オプション)
        save_path: 画像の保存先パス (オプション)
        show: 画面表示するかどうか (デフォルト: True)
        draw_dummy_nodes: Vに含まれないノードを小さな灰色点で描画するかどうか
        align_edges: 層内順序を保ったまま、エッジが横軸に近づくようy座標を調整するか
        alignment_iterations: align_edges=True のときの反復回数
        figsize: 図の大きさ(inch)。Noneなら論文の2段幅内に収まる値を自動設定
        dpi: ラスター画像の保存解像度（デフォルト: 300）
        show_legend: 図中に辺種別の凡例を表示するか
        show_layer_labels: x方向にレイヤーラベルを表示するか
        node_size: 元ノードの面積(points^2)
        dummy_node_size: ダミーノードの面積(points^2)
        font_size: ノードラベルの文字サイズ(points)
        edge_width: エッジの線幅(points)
        vertical_period: y方向の周期。Noneなら最大レイヤーサイズを使用。
            座標割当でmin_gapを変更した場合は max_layer_size * min_gap を指定
        tile_surroundings: 枠・凡例・目盛りを除いた描画領域を、周囲8方向へ
            半透明で部分配置するか。上下・左右は半分、四隅は1/4を表示する
        surrounding_opacity: 周囲8枚の不透明度（0.0から1.0）
        tile_gap: 周囲画像との間隔（pixel）
    """
    _validate_drawing_parameters(
        dpi=dpi,
        node_size=node_size,
        dummy_node_size=dummy_node_size,
        font_size=font_size,
        edge_width=edge_width,
        alignment_iterations=alignment_iterations,
    )
    if not L:
        raise ValueError("L must contain at least one layer")
    if tile_surroundings:
        validate_torus_context_options(surrounding_opacity, tile_gap)
        suffix = Path(save_path).suffix.lower() if save_path is not None else None
        if suffix is not None and suffix not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".tif",
            ".tiff",
        }:
            raise ValueError(
                "tile_surroundings requires a raster save_path "
                "(.png, .jpg, .jpeg, .webp, .tif, or .tiff)"
            )

    t_val = {} if t_val is None else t_val
    psi = {} if psi is None else psi
    node_order = _complete_node_order(order, L)

    # レイヤーキーをソートして連番インデックスにマップ
    sorted_layers = sorted(L.keys())
    layer_index = {layer: i for i, layer in enumerate(sorted_layers)}

    # 各ノードがどのレイヤーに属するかを記録
    node_to_layer = {}
    for layer_num, nodes in L.items():
        for node in nodes:
            node_to_layer[node] = layer_num

    # 描画域のサイズを計算
    num_layers = len(sorted_layers)
    max_layer_size = max(len(nodes) for nodes in L.values())

    period = float(max_layer_size if vertical_period is None else vertical_period)
    if not math.isfinite(period) or period <= 0:
        raise ValueError("vertical_period must be a finite positive number")
    coordinate_gap = period / max(max_layer_size, 1)

    # 描画域の物理的な幅・高さ（境界間の距離がトーラス周期）
    x_min, x_max = -0.5, num_layers - 0.5
    y_min, y_max = -coordinate_gap / 2.0, period - coordinate_gap / 2.0

    if pos is None:
        pos = _assign_positions(
            A=A,
            psi=psi,
            node_order=node_order,
            sorted_layers=sorted_layers,
            layer_index=layer_index,
            vertical_period=period,
            coordinate_gap=coordinate_gap,
            align_edges=align_edges,
            alignment_iterations=alignment_iterations,
        )

    _validate_positions(pos, L, A, x_min, x_max, y_min, y_max)

    V_set = set(V)
    dummy_nodes = [node for nodes in L.values() for node in nodes if node not in V_set]

    # エッジを分類
    # 左右巻きと上下巻きは排他的ではない。両方を持つ辺は複合辺として扱う。

    # ダミーノードの表示有無にかかわらず、交差削減と座標割り当てで使った
    # 分割セグメントをそのまま描画する。draw_dummy_nodes はマーカーの表示だけを
    # 制御し、元ノード間を直結して経路を変えることはしない。
    left_right_torus = []  # 左右のトーラス
    positive_wrap_edges = []  # 表示上の下端から上端へ継続（psi > 0）
    negative_wrap_edges = []  # 表示上の上端から下端へ継続（psi < 0）
    horizontal_positive_wrap_edges = []
    horizontal_negative_wrap_edges = []
    normal_edges = []

    for u, v in A:
        is_lr_torus = bool(t_val.get((u, v), False))
        winding = psi.get((u, v), 0)

        if is_lr_torus and winding > 0:
            horizontal_positive_wrap_edges.append((u, v))
        elif is_lr_torus and winding < 0:
            horizontal_negative_wrap_edges.append((u, v))
        elif is_lr_torus:
            left_right_torus.append((u, v))
        elif winding > 0:
            positive_wrap_edges.append((u, v))
        elif winding < 0:
            negative_wrap_edges.append((u, v))
        else:
            normal_edges.append((u, v))

    if figsize is None:
        figsize = _paper_figure_size(
            num_layers, max_layer_size, show_legend and not tile_surroundings
        )

    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)
    ax.set_facecolor("white")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_yticks([])
    if show_layer_labels and not tile_surroundings:
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
        # The rectangle is the fundamental domain; opposite sides are identified.
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

    def node_shrink(node):
        if node not in V_set and not draw_dummy_nodes:
            return 0.0
        size = node_size if node in V_set else dummy_node_size
        return math.sqrt(size / math.pi) + 0.8

    def edge_has_arrow(target):
        # 分割辺の途中にある非表示ダミーノードには矢印を置かず、元辺の
        # 終点に到達する最後のセグメントだけに矢印を付ける。
        return draw_dummy_nodes or target in V_set

    # 通常エッジを描画
    for u, v in normal_edges:
        _add_edge_patch(
            ax,
            pos[u],
            pos[v],
            EDGE_STYLES["normal"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_a=node_shrink(u),
            shrink_b=node_shrink(v),
        )

    # 左右のトーラス辺を描画（既存実装と同じ）
    for u, v in left_right_torus:
        u_pos = pos[u]
        v_pos = pos[v]

        dist_to_right = x_max - u_pos[0]
        dist_from_left = v_pos[0] - x_min
        total_x_dist = dist_to_right + dist_from_left
        slope = (v_pos[1] - u_pos[1]) / total_x_dist
        boundary_y = u_pos[1] + slope * dist_to_right

        # uから右端の境界点へ
        _add_edge_patch(
            ax,
            u_pos,
            (x_max, boundary_y),
            EDGE_STYLES["horizontal_wrap"],
            edge_width,
            arrow=False,
            shrink_a=node_shrink(u),
        )

        # 左端の境界点からvへ
        _add_edge_patch(
            ax,
            (x_min, boundary_y),
            v_pos,
            EDGE_STYLES["horizontal_wrap"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_b=node_shrink(v),
        )

    # 左右と上下の境界を同時にまたぐ辺を描画する。普遍被覆上では
    # (v.x + 横周期, v.y + ψ * 縦周期) への直線になり、境界を横切る
    # 順番に分割して基本領域へ折り返す。
    combined_wrap_groups = (
        (
            horizontal_positive_wrap_edges,
            1,
            EDGE_STYLES["horizontal_positive_wrap"],
        ),
        (
            horizontal_negative_wrap_edges,
            -1,
            EDGE_STYLES["horizontal_negative_wrap"],
        ),
    )
    for edges, vertical_winding, style in combined_wrap_groups:
        for u, v in edges:
            segments = _periodic_edge_segments(
                pos[u],
                pos[v],
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                horizontal_winding=1,
                vertical_winding=vertical_winding,
            )
            for index, (start, end) in enumerate(segments):
                _add_edge_patch(
                    ax,
                    start,
                    end,
                    style,
                    edge_width,
                    arrow=(
                        index == len(segments) - 1 and edge_has_arrow(v)
                    ),
                    shrink_a=node_shrink(u) if index == 0 else 0.0,
                    shrink_b=node_shrink(v) if index == len(segments) - 1 else 0.0,
                )

    # 上下のトーラス辺を描画（rayをまたぐ）
    # psi > 0: 表示上は下端から上端へ継続する。
    for u, v in positive_wrap_edges:
        u_pos = pos[u]
        v_pos = pos[v]

        # 座標系の y_max 側（invert後は下端）を通る経路
        dist_to_top = y_max - u_pos[1]
        dist_from_bottom = v_pos[1] - y_min
        total_y_dist = dist_to_top + dist_from_bottom
        slope = (v_pos[0] - u_pos[0]) / total_y_dist
        boundary_x = u_pos[0] + slope * dist_to_top

        _add_edge_patch(
            ax,
            u_pos,
            (boundary_x, y_max),
            EDGE_STYLES["positive_wrap"],
            edge_width,
            arrow=False,
            shrink_a=node_shrink(u),
        )

        _add_edge_patch(
            ax,
            (boundary_x, y_min),
            v_pos,
            EDGE_STYLES["positive_wrap"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_b=node_shrink(v),
        )

    # psi < 0: 表示上は上端から下端へ継続する。
    for u, v in negative_wrap_edges:
        u_pos = pos[u]
        v_pos = pos[v]

        # 座標系の y_min 側（invert後は上端）を通る経路
        dist_to_bottom = u_pos[1] - y_min
        dist_from_top = y_max - v_pos[1]
        total_y_dist = dist_to_bottom + dist_from_top
        slope = (v_pos[0] - u_pos[0]) / total_y_dist
        boundary_x = u_pos[0] + slope * dist_to_bottom

        _add_edge_patch(
            ax,
            u_pos,
            (boundary_x, y_min),
            EDGE_STYLES["negative_wrap"],
            edge_width,
            arrow=False,
            shrink_a=node_shrink(u),
        )

        _add_edge_patch(
            ax,
            (boundary_x, y_max),
            v_pos,
            EDGE_STYLES["negative_wrap"],
            edge_width,
            arrow=edge_has_arrow(v),
            shrink_b=node_shrink(v),
        )

    # ノードを描画
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
            linewidths=0.8,
            zorder=3,
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
            linewidths=0.35,
            marker="o",
            zorder=3,
        )

    if show_legend and not tile_surroundings:
        present_styles = []
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
        handles = [
            _legend_handle(EDGE_STYLES[key], edge_width) for key in present_styles
        ]
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

    # y軸を反転（上から下に描画）
    ax.invert_yaxis()

    if tile_surroundings:
        # 元のFigureを一度メモリ上の画像にし、中心＋周囲8方向へ合成する。
        # Axesのデータ領域だけを余白ゼロで切り出すことで、隣の基本領域と
        # 境界が直接つながるようにする。
        fig.canvas.draw()
        axes_bbox = ax.get_window_extent().transformed(
            fig.dpi_scale_trans.inverted()
        )
        fig.set_layout_engine(None)
        buffer = BytesIO()
        with plt.rc_context(
            {"pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none"}
        ):
            fig.savefig(
                buffer,
                format="png",
                dpi=dpi,
                bbox_inches=axes_bbox,
                pad_inches=0,
                facecolor="white",
            )
        buffer.seek(0)
        with Image.open(buffer) as rendered:
            tiled_image = create_torus_context_image(
                rendered,
                opacity=surrounding_opacity,
                gap=tile_gap,
                output_path=save_path,
                border_width=1,
                border_color=(0, 0, 0, 72),
            )
        buffer.close()

        # plt.show() は開いている全Figureを表示するため、タイル表示を作る前に
        # 元の小さいFigureを閉じる。
        plt.close(fig)

        if show:
            tiled_fig, tiled_ax = plt.subplots(
                figsize=(fig.get_figwidth() * 2, fig.get_figheight() * 2),
                constrained_layout=True,
            )
            tiled_ax.imshow(tiled_image)
            tiled_ax.set_axis_off()
            plt.show()
            plt.close(tiled_fig)
    elif save_path:
        # Keep labels searchable/editable in paper-oriented vector output.
        with plt.rc_context(
            {"pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none"}
        ):
            fig.savefig(
                save_path,
                dpi=dpi,
                bbox_inches="tight",
                pad_inches=0.04,
                facecolor="white",
            )
    if show and not tile_surroundings:
        plt.show()
    plt.close(fig)


def _validate_drawing_parameters(
    dpi,
    node_size,
    dummy_node_size,
    font_size,
    edge_width,
    alignment_iterations,
):
    values = {
        "dpi": dpi,
        "node_size": node_size,
        "dummy_node_size": dummy_node_size,
        "font_size": font_size,
        "edge_width": edge_width,
    }
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a finite positive number")
    if (
        isinstance(alignment_iterations, bool)
        or not isinstance(alignment_iterations, int)
        or alignment_iterations < 0
    ):
        raise ValueError("alignment_iterations must be a non-negative integer")


def _complete_node_order(order, layer_dict):
    node_to_layer = {}
    for layer, nodes in layer_dict.items():
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"L[{layer!r}] contains duplicate nodes")
        for node in nodes:
            if node in node_to_layer:
                raise ValueError(
                    f"node {node!r} occurs in both layer "
                    f"{node_to_layer[node]!r} and layer {layer!r}"
                )
            node_to_layer[node] = layer

    if order is None:
        return {layer: list(nodes) for layer, nodes in layer_dict.items()}

    unknown_layers = [
        layer for layer, nodes in order.items() if layer not in layer_dict and nodes
    ]
    if unknown_layers:
        raise ValueError(f"order contains unknown layers: {unknown_layers!r}")

    completed = {}
    for layer, layer_nodes in layer_dict.items():
        nodes = list(order.get(layer, []))
        if len(nodes) != len(set(nodes)):
            raise ValueError(f"order[{layer!r}] contains duplicate nodes")
        unknown_nodes = [node for node in nodes if node not in layer_nodes]
        if unknown_nodes:
            raise ValueError(
                f"order[{layer!r}] contains nodes outside the layer: {unknown_nodes!r}"
            )
        seen = set(nodes)
        completed[layer] = nodes + [node for node in layer_nodes if node not in seen]
    return completed


def _validate_positions(pos, layer_dict, edges, x_min, x_max, y_min, y_max):
    required_nodes = {node for nodes in layer_dict.values() for node in nodes}
    for edge in edges:
        if not isinstance(edge, tuple) or len(edge) != 2:
            raise ValueError(f"invalid edge: {edge!r}")
        if edge[0] not in required_nodes or edge[1] not in required_nodes:
            raise ValueError(f"edge endpoint is missing from L: {edge!r}")

    missing = required_nodes - set(pos)
    if missing:
        raise ValueError(
            "pos is missing layered nodes: " f"{sorted(missing, key=repr)!r}"
        )

    tolerance = 1e-9
    for node in required_nodes:
        value = pos[node]
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError(f"pos[{node!r}] must be an (x, y) pair")
        x, y = value
        if not all(
            isinstance(item, (int, float)) and math.isfinite(item) for item in value
        ):
            raise ValueError(f"pos[{node!r}] must contain finite coordinates")
        if not x_min + tolerance < x < x_max - tolerance:
            raise ValueError(f"pos[{node!r}] lies outside the horizontal domain")
        if not y_min + tolerance < y < y_max - tolerance:
            raise ValueError(f"pos[{node!r}] lies outside the vertical domain")


def _paper_figure_size(num_layers, max_layer_size, show_legend):
    width = min(7.2, max(3.4, 0.72 * num_layers + 1.2))
    data_ratio = num_layers / max(max_layer_size, 1)
    height = width / max(data_ratio, 0.65)
    height = min(5.4, max(2.4, height))
    if show_legend:
        height = min(5.8, height + 0.3)
    return (width, height)


def _add_edge_patch(
    ax,
    start,
    end,
    style,
    edge_width,
    *,
    arrow,
    shrink_a=0.0,
    shrink_b=0.0,
):
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


def _periodic_edge_segments(
    start,
    end,
    *,
    x_min,
    x_max,
    y_min,
    y_max,
    horizontal_winding,
    vertical_winding,
):
    """普遍被覆上の直線を、基本領域内の線分列へ分割する。"""
    width = x_max - x_min
    height = y_max - y_min
    lifted_end = (
        end[0] + horizontal_winding * width,
        end[1] + vertical_winding * height,
    )

    crossing_times = [0.0, 1.0]
    crossing_times.extend(_axis_crossing_times(start[0], lifted_end[0], x_min, width))
    crossing_times.extend(_axis_crossing_times(start[1], lifted_end[1], y_min, height))
    crossing_times.sort()

    # 左右・上下の境界を同時に通る（角を通る）場合の重複を除く。
    unique_times = []
    for value in crossing_times:
        if not unique_times or not math.isclose(
            value, unique_times[-1], rel_tol=0.0, abs_tol=1e-12
        ):
            unique_times.append(value)

    dx = lifted_end[0] - start[0]
    dy = lifted_end[1] - start[1]
    segments = []
    for left_t, right_t in zip(unique_times, unique_times[1:]):
        middle_t = (left_t + right_t) / 2.0
        middle_x = start[0] + middle_t * dx
        middle_y = start[1] + middle_t * dy
        x_tile = math.floor((middle_x - x_min) / width)
        y_tile = math.floor((middle_y - y_min) / height)

        def wrapped_point(t):
            return (
                start[0] + t * dx - x_tile * width,
                start[1] + t * dy - y_tile * height,
            )

        segments.append((wrapped_point(left_t), wrapped_point(right_t)))
    return segments


def _axis_crossing_times(start, end, minimum, period):
    """開区間(start, end)にある周期境界との交差時刻を返す。"""
    delta = end - start
    if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=1e-15):
        return []

    lower = min(start, end)
    upper = max(start, end)
    first_index = math.floor((lower - minimum) / period) + 1
    last_index = math.ceil((upper - minimum) / period) - 1
    times = []
    for index in range(first_index, last_index + 1):
        boundary = minimum + index * period
        t = (boundary - start) / delta
        if 0.0 < t < 1.0:
            times.append(t)
    return times


def _legend_handle(style, edge_width):
    return Line2D(
        [0],
        [0],
        color=style["color"],
        linestyle=style["linestyle"],
        linewidth=edge_width,
        label=style["label"],
    )


def _assign_positions(
    A,
    psi,
    node_order,
    sorted_layers,
    layer_index,
    vertical_period,
    coordinate_gap,
    align_edges,
    alignment_iterations,
):
    center_y = (vertical_period - coordinate_gap) / 2.0
    y_by_node = {}

    for layer_num in sorted_layers:
        nodes = node_order[layer_num]
        centered_y = _centered_positions(len(nodes), center_y, coordinate_gap)
        for node, y in zip(nodes, centered_y):
            y_by_node[node] = y

    if align_edges:
        adjacency = defaultdict(list)
        for u, v in A:
            if u in y_by_node and v in y_by_node:
                winding = psi.get((u, v), 0)
                adjacency[u].append((v, winding * vertical_period))
                adjacency[v].append((u, -winding * vertical_period))

        for _ in range(alignment_iterations):
            next_y = dict(y_by_node)
            for layer_num in sorted_layers:
                nodes = node_order[layer_num]
                if not nodes:
                    continue

                targets = []
                for node in nodes:
                    neighbors = adjacency.get(node, [])
                    if neighbors:
                        neighbor_y = sum(
                            y_by_node[neighbor] + offset
                            for neighbor, offset in neighbors
                        ) / len(neighbors)
                        targets.append(0.7 * neighbor_y + 0.3 * y_by_node[node])
                    else:
                        targets.append(y_by_node[node])

                projected = _project_ordered_centered(
                    targets,
                    center_y,
                    min_gap=coordinate_gap,
                    max_span=max(0.0, vertical_period - coordinate_gap),
                )
                for node, y in zip(nodes, projected):
                    next_y[node] = y
            y_by_node = next_y

    pos = {}
    for layer_num in sorted_layers:
        x = float(layer_index[layer_num])
        nodes = node_order[layer_num]
        for node in nodes:
            pos[node] = (x, y_by_node[node])

    return pos


def _centered_positions(count, center_y, spacing=1.0):
    if count == 0:
        return []
    start = center_y - (count - 1) * spacing / 2.0
    return [start + idx * spacing for idx in range(count)]


def _project_ordered_centered(targets, center_y, min_gap=1.0, max_span=None):
    if not targets:
        return []

    shifted_targets = [target - idx * min_gap for idx, target in enumerate(targets)]
    fitted = _isotonic_non_decreasing(shifted_targets)
    positions = [value + idx * min_gap for idx, value in enumerate(fitted)]

    if max_span is not None and positions[-1] - positions[0] > max_span:
        return _centered_positions(len(targets), center_y, min_gap)

    mean_y = sum(positions) / len(positions)
    shift = center_y - mean_y
    return [position + shift for position in positions]


def _isotonic_non_decreasing(values):
    blocks = []
    for idx, value in enumerate(values):
        blocks.append({"sum": value, "weight": 1, "start": idx, "end": idx})
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            if left["sum"] / left["weight"] <= right["sum"] / right["weight"]:
                break
            merged = {
                "sum": left["sum"] + right["sum"],
                "weight": left["weight"] + right["weight"],
                "start": left["start"],
                "end": right["end"],
            }
            blocks[-2:] = [merged]

    fitted = [0.0] * len(values)
    for block in blocks:
        value = block["sum"] / block["weight"]
        for idx in range(block["start"], block["end"] + 1):
            fitted[idx] = value
    return fitted
