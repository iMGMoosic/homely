from homely.render.canvas import Canvas
from homely.render.fonts import get_font
from homely.render.size import Size
from homely.render.text import Marquee, fit_text, truncate


def test_truncate():
    f = get_font("6x10")
    assert truncate("Hello", f, 60) == "Hello"
    out = truncate("Hello world this is long", f, 60)
    assert f.measure(out) <= 60 and out.endswith("…")


def test_fit_text_picks_largest_that_fits():
    fonts = [get_font("10x20"), get_font("7x13"), get_font("5x8")]
    font, s = fit_text("12:34", fonts, 64)
    assert font.name == "10x20" and s == "12:34"
    font, s = fit_text("12:34:56", fonts, 64)
    assert font.name == "7x13"
    font, s = fit_text("a very long sentence indeed", fonts, 64)
    assert font.name == "5x8" and s.endswith("…")


def test_marquee_static_when_fits():
    m = Marquee("Hi", get_font("6x10"), 64)
    assert not m.needs_scroll()
    assert m.cycle_time() == 0
    m.advance(1.0)
    assert m.offset() == 0


def test_marquee_scrolls_and_wraps():
    f = get_font("6x10")
    m = Marquee("0123456789ABCDEF", f, 32, speed=10, gap=8, pause_s=1.0)
    assert m.needs_scroll()
    assert m.scroll_distance == 96 + 8
    m.advance(1.0)
    assert m.offset() == 0  # still paused
    m.advance(1.0)
    assert m.offset() == 10
    m.advance(m.cycle_time())
    assert m.offset() == 10  # wrapped to same phase
    c = Canvas(Size(64, 10))
    m.draw(c, 0, 0, (255, 255, 255))
    img = c.snapshot()
    assert all(img.getpixel((x, y)) == (0, 0, 0) for x in range(32, 64) for y in range(10))
