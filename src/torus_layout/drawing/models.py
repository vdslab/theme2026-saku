"""描画設定と前処理済みデータ。新しい描画設定は追加しない。"""

from dataclasses import dataclass
from ..models import Node, Edge, Positions


@dataclass(frozen=True)
class DrawingOptions:
    draw_dummy_nodes: bool = False
    align_edges: bool = True
    alignment_iterations: int = 8
    figsize: tuple[float, float] | None = None
    dpi: float = 300
    show_legend: bool = True
    show_layer_labels: bool = True
    node_size: float = 260
    dummy_node_size: float = 28
    font_size: float = 8
    edge_width: float = 0.9
    vertical_period: float | None = None
    tile_surroundings: bool = False
    surrounding_opacity: float = 0.8
    tile_gap: int = 0


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
