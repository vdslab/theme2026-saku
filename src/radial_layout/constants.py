"""放射型方式のCLI・交差削減・座標・描画の既定値。"""

import math
from typing import Final

# CLIの入力設定。generatorの関数既定値とは独立。
DEFAULT_SIZE: Final = 10
DEFAULT_SEED: Final = None
DEFAULT_REWIRING_PROBABILITY: Final = 0.15
DEFAULT_ROUNDS: Final = 4
DEFAULT_INNER_RADIUS: Final = 1.8
DEFAULT_LAYER_GAP: Final = 1.8
DEFAULT_START_ANGLE: Final = math.pi / 2

# 描画。
DEFAULT_SHOW_DRAWING: Final = True
DPI: Final = 180
NODE_SIZE: Final = 430
NODE_COLOR: Final = "#a6cee3"
NODE_EDGE_COLOR: Final = "#1f4e79"
NODE_EDGE_WIDTH: Final = 0.9
FONT_SIZE: Final = 9
EDGE_COLOR: Final = "#333333"
REVERSED_EDGE_COLOR: Final = "#d62728"
EDGE_LINESTYLE: Final = "-"
REVERSED_EDGE_LINESTYLE: Final = "--"
EDGE_WIDTH: Final = 1.15
ARROW_SCALE: Final = 13
ARROW_SHRINK: Final = 13
RING_COLOR: Final = "#c7c7c7"
RING_WIDTH: Final = 0.8
RING_LINESTYLE: Final = (0, (2, 3))
FIGURE_MIN_SIDE: Final = 6.0
FIGURE_MAX_SIDE: Final = 12.0
FIGURE_RADIUS_SCALE: Final = 1.5
DRAWING_MARGIN: Final = 0.75
CURVE_SAMPLES_PER_TURN: Final = 24
CURVE_MAX_ANGLE_STEP: Final = math.radians(4)
