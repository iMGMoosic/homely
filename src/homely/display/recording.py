"""Test/CI displays."""

from __future__ import annotations

from PIL import Image

from homely.render.size import Size


class NullDisplay:
    def __init__(self, size: Size) -> None:
        self.size = size
        self.brightness = 100
        self.shown = 0

    def open(self) -> None:
        pass

    def show(self, frame: Image.Image) -> None:
        self.shown += 1

    def set_brightness(self, level: int) -> None:
        self.brightness = level

    def close(self) -> None:
        pass


class RecordingDisplay(NullDisplay):
    def __init__(self, size: Size, keep: int = 1000) -> None:
        super().__init__(size)
        self.frames: list[Image.Image] = []
        self.keep = keep

    def show(self, frame: Image.Image) -> None:
        super().show(frame)
        self.frames.append(frame.copy())
        if len(self.frames) > self.keep:
            del self.frames[0]

    @property
    def last(self) -> Image.Image | None:
        return self.frames[-1] if self.frames else None
