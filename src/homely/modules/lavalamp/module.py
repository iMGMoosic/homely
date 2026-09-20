"""Lava lamp: metaballs. Each blob is a precomputed radial falloff sprite; the sprites are
summed into a field image with Pillow (all C), then a lookup table turns field strength into
background, lava edge and lava core colors. Blobs drift up and down and merge where they meet.

A turn starts the way a real lamp does: everything pooled in one mass at the bottom, which
swells and then peels off one blob at a time as it "warms up"."""

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
    "ember": ((20, 6, 4), (200, 40, 10), (255, 220, 120)),
    "berry": ((36, 6, 40), (230, 40, 140), (255, 190, 230)),
    "cyber": ((6, 8, 30), (255, 0, 200), (0, 240, 255)),
    "mint": ((4, 26, 22), (30, 200, 150), (190, 255, 220)),
    "gold": ((28, 18, 2), (235, 150, 20), (255, 245, 180)),
    "ice": ((8, 14, 34), (110, 170, 255), (235, 250, 255)),
}
THRESHOLD = 96
WARMUP_DELAY = 1.2  # animation seconds the pool sits at the bottom before the first blob lifts
WARMUP_STAGGER = 5.0  # spread between the first and last blob leaving the pool
WARMUP_RISE = 4.5  # how long one blob takes to reach its drifting orbit
START_SWELL = 0.35  # extra radius while a blob is still part of the pool


def _ease(k: float) -> float:
    """Smoothstep, so a blob eases out of the pool instead of jerking upward."""
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


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
    start_x: float = 0.0
    start_y: float = 0.0
    release: float = 0.0  # animation time at which this blob starts leaving the pool
    risen: float = 0.0  # 0 = still in the pool, 1 = drifting freely

    @property
    def draw_radius(self) -> int:
        return max(1, round(self.radius * (1 + START_SWELL * (1 - self.risen))))


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
        n = self.settings.blobs
        cx = size.w / 2
        # The pool: blobs packed shoulder to shoulder along the bottom, close enough that the
        # metaball field merges them into one mass.
        spread = min(size.w * 0.3, base_r * 0.55 * max(1, n - 1))
        self.blobs = []
        for i in range(n):
            radius = int(base_r * self.rng.uniform(0.7, 1.15))
            u = 0.0 if n == 1 else (i / (n - 1) - 0.5) * 2  # -1 .. 1 across the pool
            x = min(max(cx + u * spread, radius * 0.3), size.w - radius * 0.3)
            # Heap the middle of the pool up a little so the mass reads as a dome, not a bar.
            y = size.h - radius * 0.35 - (1 - abs(u)) * radius * 0.8
            self.blobs.append(
                Blob(
                    x=x,
                    y=y,
                    phase=self.rng.uniform(0, 2 * math.pi),
                    rate=self.rng.uniform(0.6, 1.4),
                    wobble=self.rng.uniform(0.3, 0.8),
                    radius=radius,
                    start_x=x,
                    start_y=y,
                )
            )
        # Blobs peel off one at a time, in an order unrelated to where they sit in the pool.
        order = list(range(n))
        self.rng.shuffle(order)
        for slot, idx in enumerate(order):
            self.blobs[idx].release = WARMUP_DELAY + (0.0 if n == 1 else slot / (n - 1) * WARMUP_STAGGER)
        self.t = 0.0
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

    def on_enter(self) -> None:
        self._reset(self.ctx.size)

    def advance(self, dt: float, size: Size) -> None:
        self.t += dt * self.settings.speed / 30
        for b in self.blobs:
            # slow buoyant bob plus a sideways wobble; range keeps blobs mostly on screen
            orbit = size.h / 2 + math.sin(self.t * 0.35 * b.rate + b.phase) * (size.h / 2 - b.radius * 0.4)
            b.risen = _ease((self.t - b.release) / WARMUP_RISE)
            b.y = b.start_y + (orbit - b.start_y) * b.risen
            # Sideways drift only once the blob has let go of the pool.
            b.x += math.sin(self.t * 0.5 * b.wobble + b.phase * 2) * dt * self.settings.speed / 30 * 3 * b.risen
            b.x = min(max(b.x, b.radius * 0.3), size.w - b.radius * 0.3)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if c.size != self._size:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25), c.size)
        field = Image.new("L", (c.width, c.height), 0)
        for b in self.blobs:
            r = b.draw_radius
            sprite = _sprite(r)
            layer = Image.new("L", (c.width, c.height), 0)
            layer.paste(sprite, (int(b.x) - r, int(b.y) - r))
            field = ImageChops.add(field, layer)
        rs, gs, bs = self._lut
        c.blit(Image.merge("RGB", (field.point(rs), field.point(gs), field.point(bs))), 0, 0)
