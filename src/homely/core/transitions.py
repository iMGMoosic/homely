"""Frame transitions between modules."""

from __future__ import annotations

import random

from PIL import Image, ImageChops, ImageDraw


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


class FadeBlack(Transition):
    """Dip to black at the halfway point, then come back up on the new module."""

    name = "fade_black"

    def __init__(self, duration: float = 0.5) -> None:
        self.duration = duration

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        img, k = (prev, 1 - p * 2) if p < 0.5 else (nxt, (p - 0.5) * 2)
        return img.point(lambda v: int(v * max(0.0, min(1.0, k))))


class Slide(Transition):
    """Both frames move together: the old one is pushed off the panel by the new one."""

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


class Wipe(Transition):
    """A hard edge sweeps across, uncovering the new frame where it has passed."""

    def __init__(self, direction: str = "left", duration: float = 0.4) -> None:
        self.name = f"wipe_{direction}"
        self.direction = direction
        self.duration = duration

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        w, h = nxt.size
        out = prev.copy()
        if self.direction == "left":  # edge travels right to left
            x = w - round(w * p)
            out.paste(nxt.crop((x, 0, w, h)), (x, 0))
        elif self.direction == "right":
            x = round(w * p)
            out.paste(nxt.crop((0, 0, x, h)), (0, 0))
        elif self.direction == "up":
            y = h - round(h * p)
            out.paste(nxt.crop((0, y, w, h)), (0, y))
        else:
            y = round(h * p)
            out.paste(nxt.crop((0, 0, w, y)), (0, 0))
        return out


class Curtain(Transition):
    """The new frame opens out from the middle (or closes in from the edges)."""

    def __init__(self, axis: str = "h", duration: float = 0.45) -> None:
        self.name = f"curtain_{axis}"
        self.axis = axis
        self.duration = duration

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        w, h = nxt.size
        out = prev.copy()
        if self.axis == "h":
            half = round(w / 2 * p)
            if half:
                x0, x1 = w // 2 - half, w // 2 + half
                out.paste(nxt.crop((x0, 0, x1, h)), (x0, 0))
        else:
            half = round(h / 2 * p)
            if half:
                y0, y1 = h // 2 - half, h // 2 + half
                out.paste(nxt.crop((0, y0, w, y1)), (0, y0))
        return out


class Blinds(Transition):
    """Venetian blinds: evenly spaced bands widen until the new frame covers everything."""

    name = "blinds"

    def __init__(self, duration: float = 0.5, slats: int = 8) -> None:
        self.duration = duration
        self.slats = slats

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        w, h = nxt.size
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        pitch = max(2, w / self.slats)
        fill = pitch * p
        x = 0.0
        while x < w:
            if fill >= 1:
                draw.rectangle((round(x), 0, round(x + fill) - 1, h - 1), fill=255)
            x += pitch
        out = prev.copy()
        out.paste(nxt, (0, 0), mask)
        return out


class Iris(Transition):
    """A circle opens from the center of the panel onto the new frame."""

    name = "iris"

    def __init__(self, duration: float = 0.5) -> None:
        self.duration = duration

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        w, h = nxt.size
        radius = ((w * w + h * h) ** 0.5 / 2 + 1) * p  # +1 so the last frame covers the corners
        mask = Image.new("L", (w, h), 0)
        if radius >= 0.5:
            cx, cy = w / 2, h / 2
            ImageDraw.Draw(mask).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
        out = prev.copy()
        out.paste(nxt, (0, 0), mask)
        return out


class Dissolve(Transition):
    """Pixels swap over to the new frame in a fixed random order, like a TV dissolve."""

    name = "dissolve"

    def __init__(self, duration: float = 0.5, seed: int = 20260919) -> None:
        self.duration = duration
        self._seed = seed
        self._noise: Image.Image | None = None

    def _threshold_map(self, size: tuple[int, int]) -> Image.Image:
        if self._noise is None or self._noise.size != size:
            rng = random.Random(self._seed)
            self._noise = Image.frombytes("L", size, bytes(rng.randrange(256) for _ in range(size[0] * size[1])))
        return self._noise

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        cut = round(p * 255)
        mask = self._threshold_map(nxt.size).point(lambda v: 255 if v < cut else 0)
        out = prev.copy()
        out.paste(nxt, (0, 0), mask)
        return out


class PixelZoom(Transition):
    """The old frame coarsens into fat pixels, then the new one resolves back out of them."""

    name = "pixelate"

    def __init__(self, duration: float = 0.5) -> None:
        self.duration = duration

    @staticmethod
    def _blocky(img: Image.Image, k: float) -> Image.Image:
        """k: 0 = untouched, 1 = maximum chunk size."""
        w, h = img.size
        block = 1 + round(k * (min(w, h) / 4))
        if block <= 1:
            return img
        small = img.resize((max(1, w // block), max(1, h // block)), Image.Resampling.BOX)
        return small.resize((w, h), Image.Resampling.NEAREST)

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        if p < 0.5:
            return self._blocky(prev, p * 2)
        return self._blocky(nxt, (1 - p) * 2)


class Glitch(Transition):
    """Rows tear sideways and the two frames interleave, like a bad video cut."""

    name = "glitch"

    def __init__(self, duration: float = 0.45, seed: int | None = None) -> None:
        self.duration = duration
        self._rng = random.Random(seed)

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        p = max(0.0, min(1.0, p))
        w, h = nxt.size
        out = Image.new("RGB", (w, h))
        band = max(1, h // 8)
        y = 0
        while y < h:
            depth = min(h, y + band)
            src = nxt if self._rng.random() < p else prev
            shift = round(self._rng.uniform(-1, 1) * w * 0.25 * (1 - abs(p * 2 - 1)))
            strip = src.crop((0, y, w, depth))
            out.paste(strip, (shift, y))
            if shift > 0:
                out.paste(strip.crop((w - shift, 0, w, depth - y)), (0, y))
            elif shift < 0:
                out.paste(strip.crop((0, 0, -shift, depth - y)), (w + shift, y))
            y = depth
        return ImageChops.blend(out, nxt, p * p)


class RandomTransition(Transition):
    """Picks a different transition for every changeover."""

    name = "random"

    def __init__(self, duration: float = 0.45, seed: int | None = None) -> None:
        self.duration = duration
        self._rng = random.Random(seed)
        self._choices = [n for n in TRANSITION_NAMES if n not in ("cut", "random")]
        self._current: Transition = Fade(duration)
        self._last_p = 1.0

    def blend(self, prev: Image.Image, nxt: Image.Image, p: float) -> Image.Image:
        if p < self._last_p:  # a new changeover started
            self._current = make_transition(self._rng.choice(self._choices), self.duration)
        self._last_p = p
        return self._current.blend(prev, nxt, p)


# The order here is the order the web UI offers them in.
TRANSITION_NAMES: tuple[str, ...] = (
    "cut",
    "fade",
    "fade_black",
    "slide_left",
    "slide_right",
    "slide_up",
    "slide_down",
    "wipe_left",
    "wipe_right",
    "wipe_up",
    "wipe_down",
    "curtain_h",
    "curtain_v",
    "blinds",
    "iris",
    "dissolve",
    "pixelate",
    "glitch",
    "random",
)


def make_transition(name: str, duration: float) -> Transition:
    if name == "cut" or duration <= 0:
        return Cut()
    if name == "fade":
        return Fade(duration)
    if name == "fade_black":
        return FadeBlack(duration)
    if name.startswith("slide_"):
        return Slide(name.removeprefix("slide_"), duration)
    if name.startswith("wipe_"):
        return Wipe(name.removeprefix("wipe_"), duration)
    if name.startswith("curtain_"):
        return Curtain(name.removeprefix("curtain_"), duration)
    if name == "blinds":
        return Blinds(duration)
    if name == "iris":
        return Iris(duration)
    if name == "dissolve":
        return Dissolve(duration)
    if name == "pixelate":
        return PixelZoom(duration)
    if name == "glitch":
        return Glitch(duration)
    if name == "random":
        return RandomTransition(duration)
    raise ValueError(f"Unknown transition {name!r}")
