"""旧描画関数の入力検証・座標補完・辺分類。"""

from .. import constants

from collections.abc import Mapping
from os import PathLike
from pathlib import Path
import math
from ..models import Node, Edge, Layers, Positions, Winding
from ..validation import is_number
from .models import DrawingData
from .geometry import (
    validate_drawing_parameters,
    complete_node_order,
    validate_positions,
    assign_positions,
)
from .tiles import validate_torus_context_options


def prepare_drawing(
    V: list[Node],
    A: list[Edge],
    L: Layers,
    order: Layers | None = None,
    psi: Mapping[Edge, float] | None = None,
    t_val: Mapping[Edge, bool] | None = None,
    pos: Positions | None = None,
    save_path: str | PathLike[str] | None = None,
    show: bool = constants.DEFAULT_SHOW_DRAWING,
    draw_dummy_nodes: bool = constants.DEFAULT_DRAW_DUMMY_NODES,
    align_edges: bool = constants.DEFAULT_ALIGN_EDGES,
    alignment_iterations: int = constants.DEFAULT_DRAWING_ALIGNMENT_ITERATIONS,
    figsize: tuple[float, float] | None = None,
    dpi: float = constants.DEFAULT_DPI,
    show_legend: bool = constants.DEFAULT_SHOW_LEGEND,
    show_layer_labels: bool = constants.DEFAULT_SHOW_LAYER_LABELS,
    node_size: float = constants.DEFAULT_NODE_SIZE,
    dummy_node_size: float = constants.DEFAULT_DUMMY_NODE_SIZE,
    font_size: float = constants.DEFAULT_FONT_SIZE,
    edge_width: float = constants.DEFAULT_EDGE_WIDTH,
    vertical_period: float | None = None,
    tile_surroundings: bool = constants.DEFAULT_TILE_SURROUNDINGS,
    surrounding_opacity: float = constants.DEFAULT_SURROUNDING_OPACITY,
    tile_gap: int = constants.DEFAULT_TILE_GAP,
) -> DrawingData:
    validate_drawing_parameters(
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
                "tile_surroundings requires a raster save_path (.png, .jpg, .jpeg, .webp, .tif, or .tiff)"
            )
    t_val = {} if t_val is None else t_val
    psi = {} if psi is None else psi
    node_order = complete_node_order(order, L)
    sorted_layers = sorted(L.keys())
    layer_index = {layer: i for i, layer in enumerate(sorted_layers)}
    node_to_layer: dict[Node, int] = {}
    for layer_num, nodes in L.items():
        for node in nodes:
            node_to_layer[node] = layer_num
    num_layers = len(sorted_layers)
    max_layer_size = max((len(nodes) for nodes in L.values()))
    period = float(max_layer_size if vertical_period is None else vertical_period)
    if not math.isfinite(period) or period <= 0:
        raise ValueError("vertical_period must be a finite positive number")
    coordinate_gap = period / max(max_layer_size, 1)
    x_min, x_max = (-0.5, num_layers - 0.5)
    y_min, y_max = (-coordinate_gap / 2.0, period - coordinate_gap / 2.0)
    if pos is None:
        pos = assign_positions(
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
    validate_positions(pos, L, A, x_min, x_max, y_min, y_max)
    V_set = set(V)
    dummy_nodes = [node for nodes in L.values() for node in nodes if node not in V_set]
    left_right_torus: list[Edge] = []
    positive_wrap_edges: list[Edge] = []
    negative_wrap_edges: list[Edge] = []
    horizontal_positive_wrap_edges: list[Edge] = []
    horizontal_negative_wrap_edges: list[Edge] = []
    normal_edges: list[Edge] = []
    winding_numbers: Winding = {}
    for u, v in A:
        is_lr_torus = bool(t_val.get((u, v), False))
        winding = psi.get((u, v), 0)
        if not is_number(winding) or not math.isfinite(winding) or winding != int(winding):
            raise ValueError(f"psi must contain finite integer winding numbers: {(u, v)!r}")
        winding_numbers[u, v] = int(winding)
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
    return DrawingData(
        V,
        pos,
        sorted_layers,
        num_layers,
        max_layer_size,
        x_min,
        x_max,
        y_min,
        y_max,
        dummy_nodes,
        left_right_torus,
        positive_wrap_edges,
        negative_wrap_edges,
        horizontal_positive_wrap_edges,
        horizontal_negative_wrap_edges,
        normal_edges,
        winding_numbers,
    )
