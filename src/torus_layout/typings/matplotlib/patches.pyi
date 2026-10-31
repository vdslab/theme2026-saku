from .lines import LineStyle

class FancyArrowPatch:
    def __init__(
        self,
        posA: tuple[float, float],
        posB: tuple[float, float],
        *,
        arrowstyle: str,
        mutation_scale: float,
        shrinkA: float,
        shrinkB: float,
        color: str,
        linestyle: LineStyle,
        linewidth: float,
        alpha: float,
        capstyle: str,
        joinstyle: str,
        zorder: float,
        clip_on: bool
    ) -> None: ...

class Rectangle:
    def __init__(
        self,
        xy: tuple[float, float],
        width: float,
        height: float,
        *,
        fill: bool,
        edgecolor: str,
        linewidth: float,
        zorder: float,
        clip_on: bool
    ) -> None: ...
