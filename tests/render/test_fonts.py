from homely.render.fonts import FONTS, available_fonts, get_font
from homely.render.fonts.bdf import parse_bdf_text

TINY_BDF = """STARTFONT 2.1
FONT tiny
SIZE 6 75 75
FONTBOUNDINGBOX 3 5 0 -1
STARTPROPERTIES 2
FONT_ASCENT 4
FONT_DESCENT 1
ENDPROPERTIES
CHARS 2
STARTCHAR space
ENCODING 32
SWIDTH 500 0
DWIDTH 4 0
BBX 0 0 0 0
BITMAP
ENDCHAR
STARTCHAR I
ENCODING 73
SWIDTH 500 0
DWIDTH 4 0
BBX 1 3 1 0
BITMAP
80
80
80
ENDCHAR
ENDFONT
"""


def test_parse_tiny():
    f = parse_bdf_text(TINY_BDF, name="tiny")
    assert f.ascent == 4 and f.descent == 1 and f.line_height == 5
    assert len(f.glyphs) == 2
    g = f.glyph("I")
    assert g is not None
    assert (g.width, g.height, g.x_off, g.y_off, g.advance) == (1, 3, 1, 0, 4)
    assert g.mask.getpixel((0, 0)) == 1
    assert f.measure("I I") == 12
    # Missing glyph with no '?' present: falls back to default advance.
    assert f.glyph("Z") is None
    assert f.measure("Z") == 4


def test_bundled_fonts_load():
    names = available_fonts()
    for name in FONTS:
        assert name in names
        f = get_font(name)
        assert f.glyph("A") is not None
        assert f.measure("0123456789") > 0
        assert f.has("°"), name


def test_known_metrics():
    f = get_font("10x20")
    assert f.measure("12:34") == 50
    assert f.line_height == 20
    t = get_font("tom-thumb")
    assert t.measure("ABC") == 12
    assert t.line_height == 6
