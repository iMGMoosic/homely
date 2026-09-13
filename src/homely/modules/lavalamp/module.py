"""Lava lamp: metaballs. Each blob is a precomputed radial falloff sprite; the sprites are
summed into a field image with Pillow (all C), then a lookup table turns field strength into
background, lava edge and lava core colors. Blobs drift up and down and merge where they meet."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageChops

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.lavalamp.settings import LavaLampSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

PALETTES: dict[str, tuple[Color, Color, Color]] = {  # background, lava, core
    "classic": ((42, 10, 58), (255, 74, 28), (255, 176, 0)),
    "ocean": ((4, 18, 48), (0, 150, 220), (120, 240, 255)),
    "toxic": ((10, 24, 10), (80, 220, 40), (220, 255, 120)),
    "sunset": ((40, 10, 40), (255, 90, 120), (255, 200, 80)),
}
THRESHOLD = 96


@lru_cache(maxsize=32)
def _sprite(radius: int) -> Image.Image:
    """Radial falloff (1 - (d/r)^2)^2 scaled to 0..200 so two blobs saturate when they overlap."""
    size = radius * 2 + 1
    data = bytearray(size * size)
    r2 = radius * radius
    for y in range(size):
        for x in range(size):
            d2 = (x - radius) ** 2 + (y - radius) ** 2
            if d2 < r2:
                f = 1 - d2 / r2
                data[y * size + x] = int(200 * f * f)
    return Image.frombytes("L", (size, size), bytes(data))


@dataclass
class Blob:
    x: float
    y: float
    phase: float
    rate: float
    wobble: float
    radius: int


class LavaLampModule(Module[LavaLampSettings]):
    info = ModuleInfo(
        id="lavalamp",
        name="Lava lamp",
        description="Idle animation: slow blobs of lava rise, sink and merge.",
        tier=Tier.NEED,
        icon="lavalamp",
        default_duration_s=60,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = LavaLampSettings

    def __init__(self, ctx: ModuleContext, settings: LavaLampSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self.t = 0.0
        self._reset(ctx.size)

    def _reset(self, size: Size) -> None:
        base_r = max(3, int(min(size.w, size.h) * self.settings.blob_size / 100))
        self.blobs = [
            Blob(
                x=self.rng.uniform(base_r * 0.5, size.w - base_r * 0.5),
                y=self.rng.uniform(0, size.h),
                phase=self.rng.uniform(0, 2 * math.pi),
                rate=self.rng.uniform(0.6, 1.4),
                wobble=self.rng.uniform(0.3, 0.8),
                radius=int(base_r * self.rng.uniform(0.7, 1.15)),
            )
            for _ in range(self.settings.blobs)
        ]
        self._lut = self._build_lut()
        self._size = size

    def _colors(self) -> tuple[Color, Color, Color]:
        if self.settings.palette == "custom":
            return (
                parse_color(self.settings.background_color),
                parse_color(self.settings.lava_color),
                parse_color(self.settings.glow_color),
            )
        return PALETTES[self.settings.palette]

    def _build_lut(self) -> tuple[bytes, bytes, bytes]:
        bg, lava, core = self._colors()
        rs, gs, bs = bytearray(256), bytearray(256), bytearray(256)
        for v in range(256):
            if v < THRESHOLD:
                col = lerp(bg, lerp(bg, lava, 0.35), (v / THRESHOLD) ** 2)  # faint glow near the surface
            else:
                col = lerp(lava, core, min(1.0, (v - THRESHOLD) / (255 - THRESHOLD)) ** 1.5)
            rs[v], gs[v], bs[v] = col
        return bytes(rs), bytes(gs), bytes(bs)

    async def on_settings_changed(self, settings: LavaLampSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def advance(self, dt: float, size: Size) -> None:
        self.t += dt * self.settings.speed / 30
        for b in self.blobs:
            # slow buoyant bob plus a sideways wobble; range keeps blobs mostly on screen
            b.y = size.h / 2 + math.sin(self.t * 0.35 * b.rate + b.phase) * (size.h / 2 - b.radius * 0.4)
            b.x += math.sin(self.t * 0.5 * b.wobble + b.phase * 2) * dt * self.settings.speed / 30 * 3
            b.x = min(max(b.x, b.radius * 0.3), size.w - b.radius * 0.3)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if c.size != self._size:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25), c.size)
        field = Image.new("L", (c.width, c.height), 0)
        for b in self.blobs:
            sprite = _sprite(b.radius)
            layer = Image.new("L", (c.width, c.height), 0)
            layer.paste(sprite, (int(b.x) - b.radius, int(b.y) - b.radius))
            field = ImageChops.add(field, layer)
        rs, gs, bs = self._lut
        c.blit(Image.merge("RGB", (field.point(rs), field.point(gs), field.point(bs))), 0, 0)
