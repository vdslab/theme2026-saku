from typing import BinaryIO
from os import PathLike
from .axes import Axes
from .transforms import Transform, Bbox

class Canvas:
    def draw(self) -> None: ...

class Figure:
    axes: list[Axes]
    canvas: Canvas
    dpi_scale_trans: Transform
    def get_figwidth(self) -> float: ...
    def get_figheight(self) -> float: ...
    def set_layout_engine(self, layout: str | None = ...) -> None: ...
    def savefig(
        self,
        fname: str | PathLike[str] | BinaryIO,
        *,
        format: str | None = ...,
        dpi: float = ...,
        bbox_inches: str | Bbox = ...,
        pad_inches: float = ...,
        facecolor: str = ...
    ) -> None: ...
