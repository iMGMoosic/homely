"""Fan out to several displays (hardware + web preview)."""

from __future__ import annotations

import logging

from PIL import Image

from homely.display.base import Display
from homely.render.size import Size

log = logging.getLogger(__name__)


class CompositeDisplay:
    def __init__(self, displays: list[Display]) -> None:
        if not displays:
            raise ValueError("CompositeDisplay needs at least one display")
        sizes = {d.size for d in displays}
        if len(sizes) != 1:
            raise ValueError(f"displays disagree on size: {sizes}")
        self.displays = displays
        self.size: Size = displays[0].size

    def open(self) -> None:
        for d in self.displays:
            d.open()

    def show(self, frame: Image.Image) -> None:
        for d in self.displays:
            try:
                d.show(frame)
            except Exception:
                log.exception("display %s failed to show frame", type(d).__name__)

    def set_brightness(self, level: int) -> None:
        for d in self.displays:
            d.set_brightness(level)

    def close(self) -> None:
        for d in self.displays:
            try:
                d.close()
            except Exception:
                log.exception("display %s failed to close", type(d).__name__)
