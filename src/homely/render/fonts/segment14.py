"""A 14-segment display font, rasterized pixel-exact into a regular BitmapFont.

Segment names follow the usual convention::

        aaaaaaa
       f h i j b
       f  hij  b
        g1   g2
       e  kl m c
       e k l m c
        ddddddd

Letters are drawn as on a real alphanumeric display (uppercase only; lowercase maps to
uppercase). ``segment_font(w, h, t, gap, line_height)`` builds the font for one cell size.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from homely.render.fonts.bdf import BitmapFont, Glyph

# fmt: off
GLYPHS: dict[str, str] = {
    "0": "abcdef", "1": "bc", "2": "abg1g2ed", "3": "abg2cd", "4": "fg1g2bc",
    "5": "afg1g2cd", "6": "afg1g2edc", "7": "abc", "8": "abcdefg1g2", "9": "abfg1g2cd",
    "A": "abcefg1g2", "B": "abcdg2il", "C": "adef", "D": "abcdil", "E": "adefg1g2",
    "F": "aefg1g2", "G": "acdefg2", "H": "bcefg1g2", "I": "adil", "J": "bcde",
    "K": "efg1jm", "L": "def", "M": "bcefhj", "N": "bcefhm", "O": "abcdef",
    "P": "abefg1g2", "Q": "abcdefm", "R": "abefg1g2m", "S": "acdfg1g2", "T": "ail",
    "U": "bcdef", "V": "efjk", "W": "bcefkm", "X": "hjkm", "Y": "hjl", "Z": "adjk",
    "-": "g1g2", "+": "g1g2il", "/": "jk", "\\": "hm", "*": "g1g2hijklm", "_": "d",
    "=": "g1g2d", "<": "jm", ">": "hk", "(": "jm", ")": "hk", "[": "adef", "]": "abcd",
    "?": "abg2l", "!": "il", "'": "i", '"': "fb", ",": "k", ";": "k", "|": "il",
    "$": "acdfg1g2il", "&": "adeg1g2jl", "#": "bcefg1g2", "@": "abcdfg1g2", "%": "fjkc",
    "^": "hj", "~": "g1g2", "`": "h", "{": "jkg1", "}": "hmg2",
    " ": "",
}
# fmt: on
_SEG_TOKENS = ("g1", "g2", "a", "b", "c", "d", "e", "f", "h", "i", "j", "k", "l", "m")


def _tokens(spec: str) -> set[str]:
    out: set[str] = set()
    i = 0
    while i < len(spec):
        if spec[i] == "g" and i + 1 < len(spec) and spec[i + 1] in "12":
            out.add(spec[i : i + 2])
            i += 2
        else:
            out.add(spec[i])
            i += 1
    return out


def _render_cell(w: int, h: int, t: int, segs: set[str]) -> Image.Image:
    img = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(img)
    cx = (w - t) // 2  # center column (x range cx..cx+t-1)
    my = (h - t) // 2  # middle bar row
    right = w - t
    bottom = h - t

    def box(x0: int, y0: int, x1: int, y1: int) -> None:
        if x1 >= x0 and y1 >= y0:
            d.rectangle((x0, y0, x1, y1), fill=1)

    def diag(x0: int, y0: int, x1: int, y1: int) -> None:
        d.line((x0, y0, x1, y1), fill=1, width=1)
        if t > 1:  # thicken diagonals to match bar thickness
            d.line((x0 + 1, y0, x1 + 1, y1), fill=1, width=1)

    if "a" in segs:
        box(t, 0, right - 1, t - 1)
    if "d" in segs:
        box(t, bottom, right - 1, h - 1)
    if "f" in segs:
        box(0, t, t - 1, my - 1)
    if "e" in segs:
        box(0, my + t, t - 1, bottom - 1)
    if "b" in segs:
        box(right, t, w - 1, my - 1)
    if "c" in segs:
        box(right, my + t, w - 1, bottom - 1)
    if "g1" in segs:
        box(t, my, cx - 1, my + t - 1)
    if "g2" in segs:
        box(cx + t, my, right - 1, my + t - 1)
    if "i" in segs:
        box(cx, t, cx + t - 1, my - 1)
    if "l" in segs:
        box(cx, my + t, cx + t - 1, bottom - 1)
    # Diagonals run from the outer corner column to the center column so they still slope
    # on narrow cells (5 px wide) where "just inside" would collapse into a vertical line.
    if "h" in segs:
        diag(t - 1, t, cx, my - 1)
    if "j" in segs:
        diag(right, t, cx + t - 1, my - 1)
    if "k" in segs:
        diag(t - 1, bottom - 1, cx, my + t)
    if "m" in segs:
        diag(right, bottom - 1, cx + t - 1, my + t)
    return img


def _render_special(ch: str, w: int, h: int, t: int) -> tuple[Image.Image, int] | None:
    """Narrow punctuation: returns (mask, advance-width-without-gap) or None."""
    if ch == ":":
        img = Image.new("1", (t, h), 0)
        d = ImageDraw.Draw(img)
        y1 = (h - t) // 2 - max(1, h // 5)
        y2 = (h - t) // 2 + max(1, h // 5)
        d.rectangle((0, y1, t - 1, y1 + t - 1), fill=1)
        d.rectangle((0, y2, t - 1, y2 + t - 1), fill=1)
        return img, t
    if ch == ".":
        img = Image.new("1", (t, h), 0)
        ImageDraw.Draw(img).rectangle((0, h - t, t - 1, h - 1), fill=1)
        return img, t
    if ch == "°":
        s = t + 2
        img = Image.new("1", (s, h), 0)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, s - 1, s - 1), outline=1, fill=0)
        return img, s
    return None


@lru_cache(maxsize=32)
def segment_font(w: int, h: int, t: int = 1, gap: int = 1, line_height: int | None = None) -> BitmapFont:
    """Build a monospace 14-segment font with w x h cells, bar thickness t and `gap` px between glyphs."""
    if w < 3 or h < 5 or t < 1:
        raise ValueError("segment font needs w>=3, h>=5, t>=1")
    lh = line_height or (h + 3)
    ascent = h + 1  # one pixel of air above the cell
    descent = max(0, lh - ascent)
    glyphs: dict[int, Glyph] = {}
    advance = w + gap
    for ch, spec in GLYPHS.items():
        mask = _render_cell(w, h, t, _tokens(spec))
        g = Glyph(codepoint=ord(ch), width=w, height=h, x_off=0, y_off=0, advance=advance, mask=mask)
        glyphs[ord(ch)] = g
        if ch.isalpha():
            glyphs[ord(ch.lower())] = Glyph(**{**g.__dict__, "codepoint": ord(ch.lower())})
    for ch in (":", ".", "°"):
        special = _render_special(ch, w, h, t)
        if special is not None:
            mask, width = special
            glyphs[ord(ch)] = Glyph(
                codepoint=ord(ch), width=width, height=h, x_off=0, y_off=0, advance=width + gap, mask=mask
            )
    # Unknown characters render as a blank cell (like a display that has no such glyph).
    blank = Image.new("1", (w, h), 0)
    glyphs[0xFFFD] = Glyph(codepoint=0xFFFD, width=w, height=h, x_off=0, y_off=0, advance=advance, mask=blank)
    return BitmapFont(
        name=f"seg{w}x{h}",
        ascent=ascent,
        descent=descent,
        default_advance=advance,
        glyphs=glyphs,
        fallback_codepoint=0xFFFD,
    )
