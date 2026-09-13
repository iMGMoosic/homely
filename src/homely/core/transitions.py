"""Frame transitions between modules."""

from __future__ import annotations

from PIL import Image


class Transition:
    name = "cut"
    duration: float = 0.0

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        return nxt


class Cut(Transition):
    pass


class Fade(Transition):
    name = "fade"

    def __init__(self, duration: float = 0.4) -> None:
        self.duration = duration

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        return Image.blend(prev, nxt, max(0.0, min(1.0, p)))


class Slide(Transition):
    def __init__(self, direction: str = "left", duration: float = 0.4) -> None:
        self.name = f"slide_{direction}"
        self.direction = direction
        self.duration = duration

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        w, h = nxt.size
        out = Image.new("RGB", (w, h))
        if self.direction == "left":
            dx = round(w * p)
            out.paste(prev, (-dx, 0))
            out.paste(nxt, (w - dx, 0))
        elif self.direction == "right":
            dx = round(w * p)
            out.paste(prev, (dx, 0))
            out.paste(nxt, (dx - w, 0))
        elif self.direction == "up":
            dy = round(h * p)
            out.paste(prev, (0, -dy))
            out.paste(nxt, (0, h - dy))
        else:
            dy = round(h * p)
            out.paste(prev, (0, dy))
            out.paste(nxt, (0, dy - h))
        return out


def make_transition(name: str, duration: float) -> Transition:
    if name == "cut" or duration <= 0:
        return Cut()
    if name == "fade":
        return Fade(duration)
    if name.startswith("slide_"):
        return Slide(name.removeprefix("slide_"), duration)
    raise ValueError(f"Unknown transition {name!r}")
