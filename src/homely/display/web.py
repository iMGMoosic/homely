"""WebDisplay: publishes frames to the FrameBus for the browser live preview."""

from __future__ import annotations

from PIL import Image

from homely.display.framebus import FrameBus
from homely.render.size import Size


class WebDisplay:
    def __init__(self, bus: FrameBus, size: Size) -> None:
        self.bus = bus
        self.size = size

    def open(self) -> None:
        pass

    def show(self, frame: Image.Image) -> None:
        self.bus.publish(frame)

    def set_brightness(self, level: int) -> None:
        self.bus.set_brightness(level)

    def close(self) -> None:
        pass
