"""Tiny pixel-art icons defined as strings. Each character maps to a palette color.

Icons are drawn procedurally so there are no image assets or licensing to manage.
``draw_icon(canvas, x, y, ICON, palette)`` paints one; '.' is transparent.
"""

from __future__ import annotations

from homely.render.canvas import Canvas
from homely.render.color import Color

Palette = dict[str, Color]

Icon = tuple[str, ...]  # rows of equal length


def icon_size(icon: Icon) -> tuple[int, int]:
    return (len(icon[0]) if icon else 0, len(icon))


def draw_icon(canvas: Canvas, x: int, y: int, icon: Icon, palette: Palette) -> None:
    for row_i, row in enumerate(icon):
        for col_i, ch in enumerate(row):
            if ch == ".":
                continue
            color = palette.get(ch)
            if color is not None:
                canvas.pixel(x + col_i, y + row_i, color)


def scale_icon(icon: Icon, factor: int) -> Icon:
    """Integer-upscale an icon (each pixel becomes factor x factor)."""
    if factor <= 1:
        return icon
    out: list[str] = []
    for row in icon:
        wide = "".join(ch * factor for ch in row)
        out.extend([wide] * factor)
    return tuple(out)
