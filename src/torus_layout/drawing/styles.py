"""既存の辺の配色・線種・凡例。"""

from typing import TypedDict


class EdgeStyle(TypedDict):
    color: str
    linestyle: str | tuple[float, tuple[float, ...]]
    label: str


EDGE_STYLES: dict[str, EdgeStyle] = {
    "normal": {"color": "#333333", "linestyle": "-", "label": "Ordinary"},
    "horizontal_wrap": {
        "color": "#D55E00",
        "linestyle": (0, (5, 2)),
        "label": "Horizontal wrap",
    },
    "positive_wrap": {
        "color": "#0072B2",
        "linestyle": (0, (3, 1.5, 1, 1.5)),
        "label": "$\\psi=+1$: bottom-to-top",
    },
    "negative_wrap": {
        "color": "#CC79A7",
        "linestyle": (0, (1.5, 1.5)),
        "label": "$\\psi=-1$: top-to-bottom",
    },
    "horizontal_positive_wrap": {
        "color": "#009E73",
        "linestyle": (0, (5, 1.5, 1, 1.5)),
        "label": "Horizontal + $\\psi=+1$",
    },
    "horizontal_negative_wrap": {
        "color": "#882255",
        "linestyle": (0, (5, 1.5, 1, 1.5)),
        "label": "Horizontal + $\\psi=-1$",
    },
}
