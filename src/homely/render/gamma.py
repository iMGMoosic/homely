"""Gamma correction lookup tables applied only on the hardware display path."""

from __future__ import annotations

from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=8)
def build_lut(gamma: float) -> tuple[int, ...]:
    """A 768-entry LUT (3 x 256) usable with Image.point on an RGB image."""
    if gamma <= 0:
        raise ValueError("gamma must be > 0")
    table = [round(255 * ((i / 255.0) ** gamma)) for i in range(256)]
    return tuple(table * 3)


def apply_gamma(image: Image.Image, gamma: float) -> Image.Image:
    """Return a gamma-corrected copy; gamma == 1.0 returns the image unchanged."""
    if abs(gamma - 1.0) < 1e-6:
        return image
    return image.point(list(build_lut(gamma)))
