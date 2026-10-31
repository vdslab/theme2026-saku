from ..validation import is_image_path, is_integer, is_number, is_sequence

"""既存のタイル画像の合成・保存。"""
from pathlib import Path
from os import PathLike
import math
from PIL import Image, ImageDraw

type Color = tuple[int, int, int, int] | list[int]


def create_torus_context_image(
    image: Image.Image | str | PathLike[str],
    *,
    opacity: float = 0.2,
    gap: int = 0,
    output_path: str | PathLike[str] | None = None,
    background: Color = (255, 255, 255, 0),
    border_width: int = 0,
    border_color: Color = (0, 0, 0, 72),
) -> Image.Image:
    """中心画像の周囲8方向に、半透明の同一画像の一部を配置する。

    中央画像を大きく見せるため、上下には中央へ接する半分、左右には
    中央へ接する半分、四隅には中央へ接する1/4だけを表示する。

    Args:
        image: 入力画像のパス、または ``PIL.Image.Image``。
        opacity: 周囲8枚の不透明度。0.0（透明）から1.0（不透明）。
        gap: タイル間の間隔（pixel）。
        output_path: 指定した場合は合成結果を保存する。
        background: 出力キャンバスのRGBA背景色。
        border_width: 中央領域の境界線幅（pixel）。0なら描画しない。
        border_color: 境界線のRGBA色。

    Returns:
        中央の1枚と、部分表示した周囲8方向を合成した
        ``PIL.Image.Image`` (RGBA)。中心画像の不透明度は変更せず、
        元画像が持つアルファ値も維持する。
    """
    validate_torus_context_options(opacity, gap, background, border_width, border_color)
    source = load_rgba_image(image)
    width, height = source.size
    x_split = width // 2
    y_split = height // 2
    left_band_width = width - x_split
    top_band_height = height - y_split
    center_x = left_band_width + gap
    center_y = top_band_height + gap
    canvas = Image.new(
        "RGBA", (width * 2 + gap * 2, height * 2 + gap * 2), tuple(background)
    )
    faded = source.copy()

    def alpha_value(alpha: float) -> int:
        return round(alpha * opacity)

    faded.putalpha(source.getchannel("A").point(alpha_value))
    placements = [
        ((x_split, y_split, width, height), (0, 0)),
        ((0, y_split, width, height), (center_x, 0)),
        ((0, y_split, x_split, height), (center_x + width + gap, 0)),
        ((x_split, 0, width, height), (0, center_y)),
        ((0, 0, width, height), (center_x, center_y)),
        ((0, 0, x_split, height), (center_x + width + gap, center_y)),
        ((x_split, 0, width, y_split), (0, center_y + height + gap)),
        ((0, 0, width, y_split), (center_x, center_y + height + gap)),
        ((0, 0, x_split, y_split), (center_x + width + gap, center_y + height + gap)),
    ]
    for index, (crop_box, position) in enumerate(placements):
        tile = source if index == 4 else faded
        cropped = tile.crop(crop_box)
        canvas.alpha_composite(cropped, position)
    if border_width:
        draw_inner_border(
            canvas,
            left=center_x,
            top=center_y,
            width=width,
            height=height,
            border_width=border_width,
            border_color=border_color,
        )
    if output_path is not None:
        save_image(canvas, output_path)
    return canvas


def load_rgba_image(image: Image.Image | str | PathLike[str]) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGBA")
    if is_image_path(image):
        with Image.open(image) as opened:
            return opened.convert("RGBA")
    raise TypeError("image must be a path or PIL.Image.Image")


def validate_torus_context_options(
    opacity: float = 0.2,
    gap: int = 0,
    background: Color = (255, 255, 255, 0),
    border_width: int = 0,
    border_color: Color = (0, 0, 0, 72),
) -> None:
    """合成オプションを検証する。値が不正な場合は ``ValueError`` を送出する。"""
    if (
        isinstance(opacity, bool)
        or not is_number(opacity)
        or (not math.isfinite(opacity))
        or (not 0.0 <= opacity <= 1.0)
    ):
        raise ValueError("opacity must be a finite number between 0.0 and 1.0")
    if isinstance(gap, bool) or not is_integer(gap) or gap < 0:
        raise ValueError("gap must be a non-negative integer")
    if (
        isinstance(border_width, bool)
        or not is_integer(border_width)
        or border_width < 0
    ):
        raise ValueError("border_width must be a non-negative integer")
    validate_rgba("background", background)
    validate_rgba("border_color", border_color)


def validate_rgba(name: str, color: Color) -> None:
    if (
        not is_sequence(color)
        or len(color) != 4
        or any(
            (
                isinstance(channel, bool)
                or not is_integer(channel)
                or (not 0 <= channel <= 255)
                for channel in color
            )
        )
    ):
        raise ValueError(f"{name} must contain four integer RGBA channels")


def draw_inner_border(
    canvas: Image.Image,
    *,
    left: int,
    top: int,
    width: int,
    height: int,
    border_width: int,
    border_color: Color,
) -> None:
    """中央領域の境界だけに半透明の枠線を重ねる。"""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        (left, top, left + width - 1, top + height - 1),
        outline=tuple(border_color),
        width=border_width,
    )
    canvas.alpha_composite(overlay)


def save_image(image: Image.Image, output_path: str | PathLike[str]) -> None:
    output_path = Path(output_path)
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        flattened = Image.new("RGB", image.size, "white")
        flattened.paste(image, mask=image.getchannel("A"))
        flattened.save(output_path)
        return
    image.save(output_path)
