import pytest

from homely.render.color import dim, hsv, lerp, parse_color, to_hex


def test_parse_and_hex_roundtrip():
    assert parse_color("#FFB000") == (255, 176, 0)
    assert parse_color("ffb000") == (255, 176, 0)
    assert parse_color("#F80") == (255, 136, 0)
    assert to_hex((255, 176, 0)) == "#FFB000"
    with pytest.raises(ValueError):
        parse_color("red")


def test_lerp_dim_hsv():
    assert lerp((0, 0, 0), (255, 255, 255), 0.5) == (128, 128, 128)
    assert lerp((0, 0, 0), (255, 255, 255), 2) == (255, 255, 255)
    assert dim((200, 100, 50), 0.5) == (100, 50, 25)
    assert hsv(0.0) == (255, 0, 0)
    assert hsv(1.0 / 3) == (0, 255, 0)
