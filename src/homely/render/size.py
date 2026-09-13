"""Display size and orientation types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SizeFamily(str, Enum):
    SQUARE = "square"
    WIDE = "wide"
    TALL = "tall"


class Orientation(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


@dataclass(frozen=True, order=True)
class Size:
    """A logical display size in pixels (already oriented)."""

    w: int
    h: int

    def __post_init__(self) -> None:
        if self.w <= 0 or self.h <= 0:
            raise ValueError(f"Size must be positive, got {self.w}x{self.h}")

    @property
    def family(self) -> SizeFamily:
        if self.w == self.h:
            return SizeFamily.SQUARE
        return SizeFamily.WIDE if self.w > self.h else SizeFamily.TALL

    @property
    def aspect(self) -> float:
        return self.w / self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    def rotated(self) -> Size:
        return Size(self.h, self.w)

    def fits_in(self, other: Size) -> bool:
        return self.w <= other.w and self.h <= other.h

    def as_tuple(self) -> tuple[int, int]:
        return (self.w, self.h)

    def __str__(self) -> str:
        return f"{self.w}x{self.h}"

    @classmethod
    def parse(cls, text: str) -> Size:
        """Parse '64x64' / '128X32'."""
        try:
            w, h = text.lower().split("x")
            return cls(int(w), int(h))
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"Invalid size {text!r}; expected WxH like 64x64") from exc


# Sizes homely intends to support. Modules declare which they render on.
SUPPORTED_SIZES: tuple[Size, ...] = (
    Size(64, 64),
    Size(32, 32),
    Size(64, 32),
    Size(32, 64),
    Size(128, 32),
    Size(32, 128),
    Size(128, 64),
    Size(64, 128),
    Size(128, 128),
)
