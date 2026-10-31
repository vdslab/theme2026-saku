from collections.abc import Sequence

type LineStyle = str | tuple[float, tuple[float, ...]]

class Line2D:
    def __init__(
        self,
        xdata: Sequence[float],
        ydata: Sequence[float],
        *,
        color: str = ...,
        linestyle: LineStyle = ...,
        linewidth: float = ...,
        label: str = ...,
        marker: str = ...,
        markerfacecolor: str = ...,
        markeredgecolor: str = ...,
        markersize: float = ...,
    ) -> None: ...
