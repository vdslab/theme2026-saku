"""描画設定と前処理済みデータ。新しい描画設定は追加しない。"""

from .. import constants

from dataclasses import dataclass
from ..models import Node, Edge, Positions


@dataclass(frozen=True)
class DrawingOptions:
    draw_dummy_nodes: bool = constants.DEFAULT_DRAW_DUMMY_NODES
    align_edges: bool = constants.DEFAULT_ALIGN_EDGES
    alignment_iterations: int = constants.DEFAULT_DRAWING_ALIGNMENT_ITERATIONS
    figsize: tuple[float, float] | None = None
    dpi: float = constants.DEFAULT_DPI
    show_legend: bool = constants.DEFAULT_SHOW_LEGEND
    show_layer_labels: bool = constants.DEFAULT_SHOW_LAYER_LABELS
    node_size: float = constants.DEFAULT_NODE_SIZE
    dummy_node_size: float = constants.DEFAULT_DUMMY_NODE_SIZE
    font_size: float = constants.DEFAULT_FONT_SIZE
    edge_width: float = constants.DEFAULT_EDGE_WIDTH
    vertical_period: float | None = None
    tile_surroundings: bool = constants.DEFAULT_TILE_SURROUNDINGS
    surrounding_opacity: float = constants.DEFAULT_SURROUNDING_OPACITY
    tile_gap: int = constants.DEFAULT_TILE_GAP


@dataclass(frozen=True)
class DrawingData:
    original_nodes: list[Node]
    positions: Positions
    sorted_layers: list[int]
    num_layers: int
    max_layer_size: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    dummy_nodes: list[Node]
    left_right_torus: list[Edge]
    positive_wrap_edges: list[Edge]
    negative_wrap_edges: list[Edge]
    horizontal_positive_wrap_edges: list[Edge]
    horizontal_negative_wrap_edges: list[Edge]
    normal_edges: list[Edge]
