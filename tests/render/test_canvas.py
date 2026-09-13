from PIL import Image

from homely.render.canvas import Canvas
from homely.render.fonts import get_font
from homely.render.size import Size

RED = (255, 0, 0)
BLUE = (0, 0, 255)


def test_pixel_rect_and_clip():
    c = Canvas(Size(8, 8))
    c.pixel(1, 1, RED)
    c.pixel(100, 100, RED)  # ignored
    assert c.get_pixel(1, 1) == RED
    c.rect(6, 6, 10, 10, fill=BLUE)  # partially off-canvas
    assert c.get_pixel(7, 7) == BLUE
    assert c.get_pixel(5, 5) == (0, 0, 0)


def test_sub_canvas_clips_and_translates():
    c = Canvas(Size(16, 16))
    s = c.sub(4, 4, 4, 4)
    s.clear(RED)
    s.pixel(10, 10, BLUE)  # outside the sub-canvas: dropped
    assert c.get_pixel(4, 4) == RED
    assert c.get_pixel(7, 7) == RED
    assert c.get_pixel(8, 8) == (0, 0, 0)
    assert c.get_pixel(14, 14) == (0, 0, 0)


def test_text_measures_and_draws():
    c = Canvas(Size(64, 16))
    f = get_font("6x10")
    w = c.text(0, 0, "AB", f, RED)
    assert w == 12
    # Something red was drawn in the first 12 columns, nothing beyond.
    img = c.snapshot()
    reds = [(x, y) for x in range(64) for y in range(16) if img.getpixel((x, y)) == RED]
    assert reds
    assert max(x for x, _ in reds) < 12


def test_text_alignment():
    c = Canvas(Size(64, 20))
    f = get_font("6x10")
    c.text(32, 0, "AAAA", f, RED, halign="center")
    img = c.snapshot()
    xs = [x for x in range(64) for y in range(20) if img.getpixel((x, y)) == RED]
    assert min(xs) >= 32 - 12 and max(xs) < 32 + 12


def test_text_clipped_in_sub_canvas():
    c = Canvas(Size(32, 10))
    s = c.sub(0, 0, 10, 10)
    s.text(0, 0, "WWWWWW", get_font("6x10"), RED)
    img = c.snapshot()
    assert all(img.getpixel((x, y)) == (0, 0, 0) for x in range(10, 32) for y in range(10))


def test_blit_rgba_uses_alpha():
    c = Canvas(Size(4, 4))
    sprite = Image.new("RGBA", (2, 2), (0, 0, 255, 0))
    sprite.putpixel((0, 0), (255, 0, 0, 255))
    c.blit(sprite, 1, 1)
    assert c.get_pixel(1, 1) == RED
    assert c.get_pixel(2, 2) == (0, 0, 0)


def test_line_and_snapshot_is_copy():
    c = Canvas(Size(8, 8))
    c.line(0, 0, 7, 7, RED)
    snap = c.snapshot()
    assert snap.getpixel((3, 3)) == RED
    c.clear()
    assert snap.getpixel((3, 3)) == RED
