"""A small BDF (Glyph Bitmap Distribution Format) parser producing Pillow masks.

We deliberately do not use PIL.BdfFontFile: it is limited to 256 glyphs and hides
per-glyph metrics we need for measuring and marquee scrolling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class Glyph:
    codepoint: int
    width: int  # bitmap bbox width
    height: int  # bitmap bbox height
    x_off: int  # BBX x offset from origin
    y_off: int  # BBX y offset (from baseline, positive = up)
    advance: int  # DWIDTH x
    mask: Image.Image  # mode "1", size (width, height); may be 0-sized


@dataclass
class BitmapFont:
    name: str
    ascent: int
    descent: int
    default_advance: int
    glyphs: dict[int, Glyph]
    fallback_codepoint: int = ord("?")

    @property
    def line_height(self) -> int:
        return self.ascent + self.descent

    @property
    def height(self) -> int:
        return self.line_height

    def has(self, ch: str) -> bool:
        return ord(ch) in self.glyphs

    def glyph(self, ch: str) -> Glyph | None:
        """Return the glyph for ch, falling back to '?' (or None if even that is missing)."""
        g = self.glyphs.get(ord(ch))
        if g is None:
            g = self.glyphs.get(self.fallback_codepoint)
        return g

    def measure(self, text: str) -> int:
        """Advance width of text in pixels (no kerning in BDF)."""
        total = 0
        for ch in text:
            g = self.glyph(ch)
            total += g.advance if g is not None else self.default_advance
        return total

    def is_monospace(self) -> bool:
        advances = {g.advance for g in self.glyphs.values() if g.codepoint >= 32}
        return len(advances) <= 1


class BdfParseError(ValueError):
    pass


def _bitmap_to_mask(rows: list[str], width: int, height: int) -> Image.Image:
    """rows are hex strings, one per bitmap row, MSB first, padded to whole bytes."""
    if width <= 0 or height <= 0:
        return Image.new("1", (max(width, 0), max(height, 0)))
    mask = Image.new("1", (width, height), 0)
    px = mask.load()
    assert px is not None
    for y, row in enumerate(rows[:height]):
        if not row:
            continue
        bits = int(row, 16)
        nbits = len(row) * 4
        for x in range(min(width, nbits)):
            if bits >> (nbits - 1 - x) & 1:
                px[x, y] = 1
    return mask


def parse_bdf(path: str | Path) -> BitmapFont:
    path = Path(path)
    with path.open("r", encoding="latin-1") as fh:
        return parse_bdf_text(fh.read(), name=path.stem)


def parse_bdf_text(text: str, *, name: str = "font") -> BitmapFont:
    lines = text.splitlines()
    if not lines or not lines[0].startswith("STARTFONT"):
        raise BdfParseError(f"{name}: not a BDF file")

    ascent: int | None = None
    descent: int | None = None
    fbb: tuple[int, int, int, int] | None = None  # w h xoff yoff
    glyphs: dict[int, Glyph] = {}
    default_char: int | None = None

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("FONTBOUNDINGBOX"):
            parts = line.split()
            fbb = (int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]))
        elif line.startswith("FONT_ASCENT"):
            ascent = int(line.split()[1])
        elif line.startswith("FONT_DESCENT"):
            descent = int(line.split()[1])
        elif line.startswith("DEFAULT_CHAR"):
            default_char = int(line.split()[1])
        elif line.startswith("STARTCHAR"):
            i, glyph = _parse_char(lines, i, name)
            if glyph is not None and glyph.codepoint >= 0:
                glyphs[glyph.codepoint] = glyph
            continue
        elif line.startswith("ENDFONT"):
            break
        i += 1

    if fbb is None:
        raise BdfParseError(f"{name}: missing FONTBOUNDINGBOX")
    if ascent is None or descent is None:
        # Derive from the bounding box: yoff is the (negative) descent.
        descent = max(0, -fbb[3])
        ascent = fbb[1] - descent

    default_advance = fbb[0]
    space = glyphs.get(32)
    if space is not None:
        default_advance = space.advance

    font = BitmapFont(
        name=name,
        ascent=ascent,
        descent=descent,
        default_advance=default_advance,
        glyphs=glyphs,
    )
    if default_char is not None and default_char in glyphs:
        font.fallback_codepoint = default_char
    return font


def _parse_char(lines: list[str], i: int, name: str) -> tuple[int, Glyph | None]:
    """Parse one STARTCHAR..ENDCHAR block starting at lines[i]. Returns (next index, glyph)."""
    encoding = -1
    advance: int | None = None
    bbx: tuple[int, int, int, int] | None = None
    rows: list[str] = []
    in_bitmap = False
    n = len(lines)
    i += 1
    while i < n:
        line = lines[i]
        if in_bitmap:
            if line.startswith("ENDCHAR"):
                break
            rows.append(line.strip())
        elif line.startswith("ENCODING"):
            parts = line.split()
            encoding = int(parts[1])
            if encoding == -1 and len(parts) > 2:
                encoding = int(parts[2])
        elif line.startswith("DWIDTH"):
            advance = int(line.split()[1])
        elif line.startswith("BBX"):
            p = line.split()
            bbx = (int(p[1]), int(p[2]), int(p[3]), int(p[4]))
        elif line.startswith("BITMAP"):
            in_bitmap = True
        elif line.startswith("ENDCHAR"):
            break
        i += 1
    i += 1  # skip ENDCHAR
    if bbx is None:
        raise BdfParseError(f"{name}: glyph at line {i} missing BBX")
    w, h, xo, yo = bbx
    if advance is None:
        advance = w + xo
    glyph = Glyph(
        codepoint=encoding,
        width=w,
        height=h,
        x_off=xo,
        y_off=yo,
        advance=advance,
        mask=_bitmap_to_mask(rows, w, h),
    )
    return i, glyph
