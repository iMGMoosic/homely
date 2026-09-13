"""Pixel-exact seven-segment digits, the classic LCD/LED clock look.

Segments (a..g) are axis-aligned rectangles, so digits stay crisp at any size::

     aaaa
    f    b
    f    b
     gggg
    e    c
    e    c
     dddd

``SegmentFont(w, h, t)`` describes a digit box (w x h) with segment thickness t.
"""

from __future__ import annotations

from dataclasses import dataclass

from homely.render.canvas import Canvas
from homely.render.color import Color

# Which segments light up for each supported character.
_GLYPHS: dict[str, str] = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
    "-": "g",
    " ": "",
    "_": "d",
    "A": "abcefg",
    "P": "abefg",
    "C": "afed",
    "E": "afged",
    "F": "afge",
    "H": "bcefg",
    "L": "fed",
    "O": "abcdef",
    "S": "afgcd",
    "U": "bcdef",
    "b": "fgedc",
    "d": "bcdeg",
    "h": "fgec",
    "n": "egc",
    "o": "gedc",
    "r": "eg",
    "t": "fged",
    "u": "edc",
}


@dataclass(frozen=True)
class SegmentFont:
    w: int  # digit width
    h: int  # digit height
    t: int = 1  # segment thickness
    gap: int = 1  # space between digits

    def __post_init__(self) -> None:
        if self.w < 3 or self.h < 5 or self.t < 1 or self.t * 3 > self.h or self.t * 2 >= self.w:
            raise ValueError(f"unusable segment font {self.w}x{self.h} t={self.t}")

    @property
    def colon_w(self) -> int:
        return self.t

    def measure(self, text: str) -> int:
        """Width of a string made of digits/letters, ':' and '.'."""
        width = 0
        for i, ch in enumerate(text):
            if i:
                width += self.gap
            width += self.colon_w if ch in ":." else self.w
        return width

    # ---- drawing ------------------------------------------------------------------

    def _segments(self, x: int, y: int) -> dict[str, tuple[int, int, int, int]]:
        """Segment rectangles (x, y, w, h) for a digit at (x, y)."""
        w, h, t = self.w, self.h, self.t
        mid = (h - t) // 2  # top of the middle bar
        inner_w = w - 2 * t  # horizontal bars sit between the verticals
        return {
            "a": (x + t, y, inner_w, t),
            "g": (x + t, y + mid, inner_w, t),
            "d": (x + t, y + h - t, inner_w, t),
            "f": (x, y + t, t, mid - t),
            "b": (x + w - t, y + t, t, mid - t),
            "e": (x, y + mid + t, t, h - mid - 2 * t),
            "c": (x + w - t, y + mid + t, t, h - mid - 2 * t),
        }

    def draw_char(self, canvas: Canvas, x: int, y: int, ch: str, color: Color, off: Color | None = None) -> int:
        """Draw one character; returns its advance width (without gap)."""
        if ch in ":.":
            self._draw_colon(canvas, x, y, color if ch == ":" else None, off, dot_only=ch == ".")
            return self.colon_w
        lit = _GLYPHS.get(ch, _GLYPHS.get(ch.upper(), ""))
        for name, (sx, sy, sw, sh) in self._segments(x, y).items():
            if name in lit:
                canvas.rect(sx, sy, sw, sh, fill=color)
            elif off is not None:
                canvas.rect(sx, sy, sw, sh, fill=off)
        return self.w

    def _draw_colon(
        self, canvas: Canvas, x: int, y: int, color: Color | None, off: Color | None, *, dot_only: bool
    ) -> None:
        t = self.t
        h = self.h
        mid = (h - t) // 2
        upper_y = y + (mid - t) // 2 + t // 2
        lower_y = y + mid + t + (h - mid - 2 * t - t) // 2
        if dot_only:
            canvas.rect(x, y + h - t, t, t, fill=color or off) if (color or off) else None
            return
        for yy in (upper_y, lower_y):
            if color is not None:
                canvas.rect(x, yy, t, t, fill=color)
            elif off is not None:
                canvas.rect(x, yy, t, t, fill=off)

    def draw(
        self,
        canvas: Canvas,
        x: int,
        y: int,
        text: str,
        color: Color,
        *,
        off: Color | None = None,
        colon_visible: bool = True,
    ) -> int:
        """Draw text left-aligned at (x, y). A hidden colon still takes its space. Returns width."""
        cx = x
        for i, ch in enumerate(text):
            if i:
                cx += self.gap
            if ch == ":" and not colon_visible:
                self._draw_colon(canvas, cx, y, None, off, dot_only=False)
                cx += self.colon_w
                continue
            cx += self.draw_char(canvas, cx, y, ch, color, off)
        return cx - x

    def draw_centered(self, canvas: Canvas, y: int, text: str, color: Color, **kw: object) -> int:
        x = (canvas.width - self.measure(text)) // 2
        return self.draw(canvas, x, y, text, color, **kw)  # type: ignore[arg-type]


def fit_segment_font(text: str, max_w: int, max_h: int, *, aspect: float = 0.55, min_t: int = 1) -> SegmentFont:
    """Largest SegmentFont whose rendering of text fits in max_w x max_h."""
    best: SegmentFont | None = None
    for h in range(max_h, 4, -1):
        t = max(min_t, round(h / 9))
        w = max(3, round(h * aspect))
        if t * 2 >= w:
            w = t * 2 + 1
        try:
            font = SegmentFont(w, h, t, gap=max(1, t))
        except ValueError:
            continue
        if font.measure(text) <= max_w:
            best = font
            break
    if best is None:
        return SegmentFont(3, 5, 1, gap=1)
    return best
