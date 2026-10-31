"""既存と同じ画像保存・表示・Figureの後処理。"""

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
    show: bool = True
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
                gap=tile_gap,
                output_path=save_path,
                border_width=1,
                border_color=(0, 0, 0, 72),
            )
        buffer.close()
        plt.close(fig)
        if show:
            tiled_fig, tiled_ax = plt.subplots(
                figsize=(fig.get_figwidth() * 2, fig.get_figheight() * 2),
                constrained_layout=True,
            )
            tiled_ax.imshow(tiled_image)
            tiled_ax.set_axis_off()
            plt.show()
            plt.close(tiled_fig)
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


def draw_layout(
    graph: SubdividedGraph,
    crossing: CrossingResult,
    coordinates: CoordinateResult | None = None,
    *,
    options: DrawingOptions | None = None,
    save_path: str | PathLike[str] | None = None,
    show: bool = True
) -> None:
    options = DrawingOptions() if options is None else options
    figure = create_figure(
        graph, crossing, coordinates, options=options, save_path=save_path
    )
    output_figure(figure, options=options, save_path=save_path, show=show)
