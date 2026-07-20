"""画像をトーラスの基本領域として 3 x 3 に並べるユーティリティ。"""

from pathlib import Path
import math
from os import PathLike

from PIL import Image, ImageDraw


def create_torus_context_image(
    image,
    *,
    opacity=0.2,
    gap=0,
    output_path=None,
    background=(255, 255, 255, 0),
    border_width=0,
    border_color=(0, 0, 0, 72),
):
    """中心画像の周囲8方向に、半透明の同一画像を配置する。

    Args:
        image: 入力画像のパス、または ``PIL.Image.Image``。
        opacity: 周囲8枚の不透明度。0.0（透明）から1.0（不透明）。
        gap: タイル間の間隔（pixel）。
        output_path: 指定した場合は合成結果を保存する。
        background: 出力キャンバスのRGBA背景色。
        border_width: 各タイルの境界線幅（pixel）。0なら描画しない。
        border_color: 境界線のRGBA色。

    Returns:
        3 x 3 に合成した ``PIL.Image.Image`` (RGBA)。中心画像の不透明度は
        変更せず、元画像が持つアルファ値も維持する。
    """
    validate_torus_context_options(
        opacity, gap, background, border_width, border_color
    )
    source = _load_rgba_image(image)

    width, height = source.size
    canvas = Image.new(
        "RGBA",
        (width * 3 + gap * 2, height * 3 + gap * 2),
        tuple(background),
    )

    faded = source.copy()
    faded.putalpha(source.getchannel("A").point(lambda alpha: round(alpha * opacity)))

    for row in range(3):
        for column in range(3):
            tile = source if (row, column) == (1, 1) else faded
            x = column * (width + gap)
            y = row * (height + gap)
            canvas.alpha_composite(tile, (x, y))

    if border_width:
        _draw_tile_borders(
            canvas,
            tile_width=width,
            tile_height=height,
            gap=gap,
            border_width=border_width,
            border_color=border_color,
        )

    if output_path is not None:
        _save_image(canvas, output_path)
    return canvas


def _load_rgba_image(image):
    if isinstance(image, Image.Image):
        return image.convert("RGBA")
    if isinstance(image, (str, PathLike)):
        with Image.open(image) as opened:
            return opened.convert("RGBA")
    raise TypeError("image must be a path or PIL.Image.Image")


def validate_torus_context_options(
    opacity=0.2,
    gap=0,
    background=(255, 255, 255, 0),
    border_width=0,
    border_color=(0, 0, 0, 72),
):
    """合成オプションを検証する。値が不正な場合は ``ValueError`` を送出する。"""
    if (
        isinstance(opacity, bool)
        or not isinstance(opacity, (int, float))
        or not math.isfinite(opacity)
        or not 0.0 <= opacity <= 1.0
    ):
        raise ValueError("opacity must be a finite number between 0.0 and 1.0")
    if isinstance(gap, bool) or not isinstance(gap, int) or gap < 0:
        raise ValueError("gap must be a non-negative integer")
    if isinstance(border_width, bool) or not isinstance(border_width, int) or border_width < 0:
        raise ValueError("border_width must be a non-negative integer")
    _validate_rgba("background", background)
    _validate_rgba("border_color", border_color)


def _validate_rgba(name, color):
    if (
        not isinstance(color, (tuple, list))
        or len(color) != 4
        or any(
            isinstance(channel, bool)
            or not isinstance(channel, int)
            or not 0 <= channel <= 255
            for channel in color
        )
    ):
        raise ValueError(f"{name} must contain four integer RGBA channels")


def _draw_tile_borders(
    canvas, *, tile_width, tile_height, gap, border_width, border_color
):
    """タイルの接続を維持したまま、半透明の輪郭線を重ねる。"""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for row in range(3):
        for column in range(3):
            left = column * (tile_width + gap)
            top = row * (tile_height + gap)
            draw.rectangle(
                (left, top, left + tile_width - 1, top + tile_height - 1),
                outline=tuple(border_color),
                width=border_width,
            )
    canvas.alpha_composite(overlay)


def _save_image(image, output_path):
    output_path = Path(output_path)
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        # JPEGにはアルファチャンネルがないため白背景へ合成する。
        flattened = Image.new("RGB", image.size, "white")
        flattened.paste(image, mask=image.getchannel("A"))
        flattened.save(output_path)
        return
    image.save(output_path)
