"""Text fitting and scrolling helpers."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from homely.render.canvas import Canvas
from homely.render.color import Color
from homely.render.fonts.bdf import BitmapFont

ELLIPSIS = "…"


class FitMode(str, Enum):
    NONE = "none"
    SHRINK = "shrink"
    TRUNCATE = "truncate"
    MARQUEE = "marquee"


def truncate(s: str, font: BitmapFont, max_w: int, ellipsis: str = ELLIPSIS) -> str:
    """Cut s so it fits in max_w pixels, appending an ellipsis if anything was cut."""
    if font.measure(s) <= max_w:
        return s
    ell = ellipsis if font.has(ellipsis) else "."
    ell_w = font.measure(ell)
    out = ""
    for ch in s:
        if font.measure(out + ch) + ell_w > max_w:
            break
        out += ch
    return out.rstrip() + ell if out else ""


def wrap_text(s: str, font: BitmapFont, max_w: int, max_lines: int = 0) -> list[str]:
    """Greedy word wrap. Long words are broken. If max_lines > 0 the last line is truncated."""
    words = s.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.measure(candidate) <= max_w:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while font.measure(word) > max_w and len(word) > 1:
            cut = len(word)
            while cut > 1 and font.measure(word[:cut]) > max_w:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        kept = lines[:max_lines]
        rest = " ".join(lines[max_lines - 1 :])
        kept[-1] = truncate(rest, font, max_w)
        return kept
    return lines


def fit_text(s: str, fonts: Sequence[BitmapFont], max_w: int) -> tuple[BitmapFont, str]:
    """Pick the first (largest) font in which s fits; else truncate in the last font."""
    if not fonts:
        raise ValueError("fit_text needs at least one font")
    for font in fonts:
        if font.measure(s) <= max_w:
            return font, s
    last = fonts[-1]
    return last, truncate(s, last, max_w)


class Marquee:
    """Stateful horizontal scroller for text wider than its box.

    Call ``advance(dt)`` once per frame then ``draw``. Scrolls left continuously with a
    pause at the start; ``cycle_time`` tells a module how long one full pass takes.
    """

    def __init__(
        self,
        text: str,
        font: BitmapFont,
        width: int,
        *,
        speed: float = 20.0,
        gap: int = 16,
        pause_s: float = 1.0,
    ) -> None:
        self.text = text
        self.font = font
        self.width = width
        self.speed = speed
        self.gap = gap
        self.pause_s = pause_s
        self.text_w = font.measure(text)
        self._t = 0.0

    def needs_scroll(self) -> bool:
        return self.text_w > self.width

    @property
    def scroll_distance(self) -> int:
        return self.text_w + self.gap

    def cycle_time(self) -> float:
        if not self.needs_scroll():
            return 0.0
        return self.pause_s + self.scroll_distance / self.speed

    def reset(self) -> None:
        self._t = 0.0

    def advance(self, dt: float) -> None:
        if not self.needs_scroll():
            return
        cycle = self.cycle_time()
        self._t = (self._t + dt) % cycle if cycle > 0 else 0.0

    def offset(self) -> int:
        """Current horizontal offset (0 = text starts at box left)."""
        if not self.needs_scroll():
            return 0
        moving = max(0.0, self._t - self.pause_s)
        return int(moving * self.speed) % self.scroll_distance

    def draw(self, canvas: Canvas, x: int, y: int, color: Color) -> None:
        if not self.needs_scroll():
            canvas.text(x, y, self.text, self.font, color)
            return
        clip = canvas.sub(x, y, self.width, self.font.line_height)
        off = self.offset()
        clip.text(-off, 0, self.text, self.font, color)
        # Draw the wrapped copy following the gap so the loop is seamless.
        clip.text(-off + self.scroll_distance, 0, self.text, self.font, color)
