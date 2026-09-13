import pytest

from homely.render.canvas import Canvas
from homely.render.segments import SegmentFont, fit_segment_font
from homely.render.size import Size


def lit(c: Canvas):
    img = c.snapshot()
    return {(x, y) for x in range(img.width) for y in range(img.height) if img.getpixel((x, y)) != (0, 0, 0)}


def test_measure_and_fit():
    f = SegmentFont(12, 22, 2, gap=2)
    assert f.measure("88:88") == 12 * 4 + 2 + 2 * 4
    fit = fit_segment_font("88:88", 60, 24)
    assert fit.measure("88:88") <= 60 and fit.h <= 24 and fit.h >= 20
    with pytest.raises(ValueError):
        SegmentFont(2, 5, 1)


def test_digit_one_only_right_side_and_colon_hidden_keeps_width():
    c = Canvas(Size(20, 12))
    f = SegmentFont(6, 10, 1)
    w = f.draw(c, 0, 1, "1", (255, 255, 255))
    assert w == 6
    xs = {x for x, _ in lit(c)}
    assert xs == {5}
    c2 = Canvas(Size(20, 12))
    w_on = f.draw(c2, 0, 1, "1:1", (255, 255, 255), colon_visible=True)
    c3 = Canvas(Size(20, 12))
    w_off = f.draw(c3, 0, 1, "1:1", (255, 255, 255), colon_visible=False)
    assert w_on == w_off == f.measure("1:1")
    assert len(lit(c2)) > len(lit(c3))


def test_ghost_segments_drawn_dim():
    c = Canvas(Size(10, 12))
    SegmentFont(6, 10, 1).draw(c, 1, 1, " ", (255, 255, 255), off=(20, 20, 20))
    assert lit(c) and all(c.get_pixel(x, y) == (20, 20, 20) for x, y in lit(c))
