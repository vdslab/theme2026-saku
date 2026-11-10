"""既存と同じ画像保存・表示・Figureの後処理。"""

from .. import constants

from os import PathLike
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from PIL import Image
from ..models import SubdividedGraph, CrossingResult, CoordinateResult
from .models import DrawingOptions
from .figure import create_figure
from .tiles import create_torus_context_image


def output_figure(
    fig: Figure,
    *,
    options: DrawingOptions,
    save_path: str | PathLike[str] | None = None,
    show: bool = constants.DEFAULT_SHOW_DRAWING
) -> None:
    ax = fig.axes[0]
    tile_surroundings = options.tile_surroundings
    dpi, surrounding_opacity, tile_gap = (
        options.dpi,
        options.surrounding_opacity,
        options.tile_gap,
    )
    if tile_surroundings:
        fig.canvas.draw()
        axes_bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
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
                gray_out=options.gray_out_surroundings,
                gap=tile_gap,
                output_path=save_path,
                border_width=1,
                border_color=(0, 0, 0, 72),
            )
        buffer.close()
        plt.close(fig)
        if show:
            show_image(tiled_image)
    elif save_path:
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
    if show and (not tile_surroundings):
        plt.show()
    plt.close(fig)


def show_image(image: Image.Image) -> None:
    """Fit a window to the image aspect ratio, with no subplot margins."""
    width, height = image.size
    scale = min(constants.DISPLAY_MAX_WIDTH / width, constants.DISPLAY_MAX_HEIGHT / height)
    figure = plt.figure(figsize=(width * scale, height * scale))
    try:
        manager = figure.canvas.manager
        if manager is not None:
            manager.set_window_title("Torus layout")
        axis = figure.add_axes((0, 0, 1, 1))
        axis.imshow(image)
        axis.set_axis_off()
        plt.show(block=True)
    finally:
        plt.close(figure)


def draw_layout(
    graph: SubdividedGraph,
    crossing: CrossingResult,
    coordinates: CoordinateResult | None = None,
    *,
    options: DrawingOptions | None = None,
    save_path: str | PathLike[str] | None = None,
    show: bool = constants.DEFAULT_SHOW_DRAWING
) -> None:
    options = DrawingOptions() if options is None else options
    figure = create_figure(
        graph, crossing, coordinates, options=options, save_path=save_path
    )
    output_figure(figure, options=options, save_path=save_path, show=show)
