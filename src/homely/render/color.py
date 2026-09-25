"""Color helpers. Colors are plain (r, g, b) tuples of 0..255 ints."""

from __future__ import annotations

import colorsys
import re

Color = tuple[int, int, int]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def parse_color(text: str) -> Color:
    """Parse '#RRGGBB', 'RRGGBB' or '#RGB' into an (r, g, b) tuple."""
    m = _HEX_RE.match(text.strip())
    if not m:
        raise ValueError(f"Invalid color {text!r}; expected #RRGGBB")
    hexpart = m.group(1)
    if len(hexpart) == 3:
        hexpart = "".join(ch * 2 for ch in hexpart)
    return (int(hexpart[0:2], 16), int(hexpart[2:4], 16), int(hexpart[4:6], 16))


def to_hex(color: Color) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def _clamp(v: float) -> int:
    return max(0, min(255, round(v)))


def hsv(h: float, s: float = 1.0, v: float = 1.0) -> Color:
    """h in [0, 1) (wraps), s and v in [0, 1]."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (_clamp(r * 255), _clamp(g * 255), _clamp(b * 255))


def lerp(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (
        _clamp(a[0] + (b[0] - a[0]) * t),
        _clamp(a[1] + (b[1] - a[1]) * t),
        _clamp(a[2] + (b[2] - a[2]) * t),
    )


def dim(color: Color, factor: float) -> Color:
    """Scale brightness by factor in [0, 1]."""
    factor = max(0.0, min(1.0, factor))
    return (_clamp(color[0] * factor), _clamp(color[1] * factor), _clamp(color[2] * factor))


def luminance(color: Color) -> float:
    """Perceived brightness in [0, 1] (Rec. 601 weights; good enough for picking text color)."""
    r, g, b = color
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def readable_on(background: Color) -> Color:
    """Black or white, whichever reads better on the given fill."""
    return (0, 0, 0) if luminance(background) > 0.55 else (255, 255, 255)


def lift(color: Color, min_value: float = 0.6) -> Color:
    """Raise a color's HSV value to at least min_value, keeping its hue.

    Brand colors are picked for paper and screens; navy, maroon and forest green all read as
    black on an LED panel. Near-greys stay grey rather than taking on a random hue.
    """
    h, s, v = colorsys.rgb_to_hsv(color[0] / 255, color[1] / 255, color[2] / 255)
    if v >= min_value:
        return color
    return hsv(h, s, min_value)


BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)
RED: Color = (255, 0, 0)
GREEN: Color = (0, 255, 0)
BLUE: Color = (0, 0, 255)
AMBER: Color = (255, 176, 0)
CYAN: Color = (0, 168, 255)
MAGENTA: Color = (255, 0, 200)
YELLOW: Color = (255, 220, 0)
ORANGE: Color = (255, 110, 0)
GRAY: Color = (110, 110, 110)
DIM_GRAY: Color = (40, 40, 40)

PALETTE: dict[str, Color] = {
    "black": BLACK,
    "white": WHITE,
    "red": RED,
    "green": GREEN,
    "blue": BLUE,
    "amber": AMBER,
    "cyan": CYAN,
    "magenta": MAGENTA,
    "yellow": YELLOW,
    "orange": ORANGE,
    "gray": GRAY,
    "dim_gray": DIM_GRAY,
}
