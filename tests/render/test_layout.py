import pytest

from homely.render.layout import (
    UnsupportedSize,
    layout,
    layout_fallback,
    layout_family,
    resolve,
    supported_sizes,
)
from homely.render.size import SUPPORTED_SIZES, Size, SizeFamily


class Square:
    @layout(64, 64)
    def r64(self, c, f):
        pass


class Wide(Square):
    @layout(64, 32)
    def r64x32(self, c, f):
        pass

    @layout_family(SizeFamily.TALL, min_h=64)
    def rtall(self, c, f):
        pass


class Anything(Wide):
    @layout_fallback
    def rany(self, c, f):
        pass


def test_exact_and_upscale_fallback():
    r = resolve(Square, Size(64, 64))
    assert r.exact and r.renderer is Square.r64
    r = resolve(Square, Size(128, 128))
    assert not r.exact and r.designed_for == Size(64, 64)
    with pytest.raises(UnsupportedSize):
        resolve(Square, Size(64, 32))


def test_family_and_inheritance():
    assert resolve(Wide, Size(128, 32)).designed_for == Size(64, 32)
    assert resolve(Wide, Size(32, 64)).renderer is Wide.rtall
    with pytest.raises(UnsupportedSize):
        resolve(Wide, Size(32, 32))
    assert resolve(Wide, Size(64, 64)).renderer is Square.r64


def test_fallback_and_supported():
    r = resolve(Anything, Size(32, 32))
    assert r.fallback and r.renderer is Anything.rany
    assert supported_sizes(Anything, SUPPORTED_SIZES) == list(SUPPORTED_SIZES)
    assert Size(32, 32) not in supported_sizes(Wide, SUPPORTED_SIZES)
