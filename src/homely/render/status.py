"""A small centred card a data module shows when it has nothing to draw yet."""

from __future__ import annotations

from homely.render.canvas import Canvas
from homely.render.color import Color, dim
from homely.render.fonts import get_font
from homely.render.text import fit_text

BACKGROUND: Color = (18, 20, 30)


def draw_status_card(c: Canvas, head: str, detail: str, color: Color) -> None:
    """A headline ("No location") and a hint ("set it in Display settings"), centred.

    Modules draw this instead of going blank when the reason is fixable: a setting is missing
    or every fetch so far has failed. The hint is dropped when the panel is too short for it.
    """
    c.clear(BACKGROUND)
    fonts = [get_font(n) for n in ("6x10", "5x8", "4x6", "tom-thumb")]
    hf, htext = fit_text(head, fonts, c.width - 2)
    df, dtext = fit_text(detail, [get_font("4x6"), get_font("tom-thumb")], c.width - 2)
    fits_detail = c.height >= hf.line_height + df.line_height + 3
    top = (c.height - (hf.line_height + (df.line_height + 2 if fits_detail else 0))) // 2
    c.text_centered(top, htext, hf, color)
    if fits_detail:
        c.text_centered(top + hf.line_height + 2, dtext, df, dim(color, 0.7))
