"""杉山方式のCLI・交差削減・座標・描画の既定値。"""

from typing import Final

# CLIの入力設定。generatorの関数既定値とは独立。
DEFAULT_SIZE: Final = 10
DEFAULT_SEED: Final = None
DEFAULT_REWIRING_PROBABILITY: Final = 0.15
DEFAULT_CROSSING_SWEEPS: Final = 12
DEFAULT_NODE_GAP: Final = 1.35
DEFAULT_LAYER_GAP: Final = 1.65

# 描画。
NODE_SIZE: Final = 400
NODE_COLOR: Final = "lightblue"
FONT_SIZE: Final = 10
EDGE_COLOR: Final = "black"
REVERSED_EDGE_COLOR: Final = "red"
EDGE_LINESTYLE: Final = "-"
REVERSED_EDGE_LINESTYLE: Final = "--"
NODE_RADIUS: Final = 0.15
ARROW_SCALE: Final = 20
FIGURE_SCALE: Final = 2
X_MARGIN: Final = 0.55
Y_MARGIN: Final = 0.65
