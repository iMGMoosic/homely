from homely.render.canvas import Canvas
from homely.render.fonts import get_font, get_theme, segment_font, set_theme
from homely.render.size import Size


def lit(mask):
    return {(x, y) for x in range(mask.width) for y in range(mask.height) if mask.getpixel((x, y))}


def test_segment_font_metrics_and_case_folding():
    f = segment_font(5, 9, 1, 1, 10)
    assert f.line_height == 10 and f.measure("AB") == 12 and f.measure("A:B") == 14
    assert lit(f.glyph("a").mask) == lit(f.glyph("A").mask)
    assert f.glyph("~unknown~"[1]).mask.getbbox() is not None  # 'u' -> 'U'
    assert f.glyph("§").mask.getbbox() is None  # unknown -> blank cell, same advance
    assert f.measure("§") == 6


def test_letter_shapes_are_distinct():
    f = segment_font(7, 11, 1)
    shapes = {ch: frozenset(lit(f.glyph(ch).mask)) for ch in "MNWVXYZOQ8B"}  # O and 0 are alike by design
    assert len(set(shapes.values())) == len(shapes)
    # '1' lights only the right-hand bars
    one = lit(f.glyph("1").mask)
    assert one and all(x == 6 for x, _ in one)


def test_theme_switch_maps_pixel_names():
    set_theme("pixel")
    assert get_font("6x10").name == "6x10"
    set_theme("segment")
    try:
        assert get_theme() == "segment"
        assert get_font("6x10").name == "seg5x9" and get_font("6x10").line_height == 10
        assert get_font("tom-thumb").name == "seg4x6" and get_font("tom-thumb").line_height == 7
        assert get_font("pixel:6x10").name == "6x10"
        assert get_font("seg:9x17:2").name == "seg9x17"
    finally:
        set_theme("pixel")


def test_outline_text():
    c = Canvas(Size(20, 12))
    c.text(2, 1, "1", segment_font(5, 9), (255, 255, 255), outline=(255, 0, 0))
    img = c.snapshot()
    assert img.getpixel((6, 5)) == (255, 255, 255)  # the bar itself (x=2+4)
    assert img.getpixel((7, 5)) == (255, 0, 0)  # halo to its right
