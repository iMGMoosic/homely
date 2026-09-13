import pytest

from homely.render.size import Orientation, Size, SizeFamily


def test_family():
    assert Size(64, 64).family is SizeFamily.SQUARE
    assert Size(128, 32).family is SizeFamily.WIDE
    assert Size(32, 128).family is SizeFamily.TALL


def test_rotated_and_fits():
    assert Size(64, 32).rotated() == Size(32, 64)
    assert Size(64, 32).fits_in(Size(128, 64))
    assert not Size(128, 32).fits_in(Size(64, 64))


def test_parse():
    assert Size.parse("64x64") == Size(64, 64)
    assert Size.parse("128X32") == Size(128, 32)
    with pytest.raises(ValueError):
        Size.parse("64")
    with pytest.raises(ValueError):
        Size(0, 10)


def test_orientation_values():
    assert Orientation("portrait") is Orientation.PORTRAIT
