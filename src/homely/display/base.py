"""Display protocol: anything that can show a frame."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PIL import Image

from homely.render.size import Size


@runtime_checkable
class Display(Protocol):
    size: Size

    def open(self) -> None: ...

    def show(self, frame: Image.Image) -> None:
        """frame is an RGB image exactly `size` big. May block briefly (vsync)."""

    def set_brightness(self, level: int) -> None:
        """0..100"""

    def close(self) -> None: ...
