"""Lava lamp: metaballs. Each blob is a precomputed radial falloff sprite; the sprites are
summed into a field image with Pillow (all C), then a lookup table turns field strength into
background, lava edge and lava core colors. Blobs drift up and down and merge where they meet.

It behaves like the real thing: a lump of lava sits pooled at the bottom centre, and blobs
peel off it one at a time -- never all at once -- to ride a convection loop up one side, across
the top and down the other, then slide back along the bottom and rejoin the lump, rest there a
while, and go round again. A turn opens with everything in the lump."""

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
WARMUP_DELAY = 1.2  # animation seconds the lump sits alone before the first blob lifts
DEPART_GAP = (2.2, 4.5)  # seconds between one blob leaving the lump and the next
REST = (3.0, 7.0)  # seconds a returning blob stays in the lump before it may go again
RESTING_SHARE = 0.4  # at least this share of the blobs is always in the lump
START_SWELL = 0.12  # extra radius while a blob is part of the lump
LOOP_PERIOD = 16.0  # animation seconds for one trip round the loop at rate 1.0
LOOP_INSET = 0.22  # how far in from each edge the rising and sinking columns sit
JOIN = 0.15  # share of a trip at each end spent easing between the lump and the loop
RAMP = 0.1  # share of a trip at each end spent speeding up or slowing down


def _ease(k: float) -> float:
    """Smoothstep, so a blob eases out of the lump instead of jerking upward."""
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def _travelled(p: float) -> float:
    """Share of the loop covered at trip progress p: a steady pace, with a gentle start as the
    blob pulls away from the lump and a gentle stop as it settles back in."""
    p = max(0.0, min(1.0, p))
    v = 1 / (1 - RAMP)
    if p < RAMP:
        return v * p * p / (2 * RAMP)
    if p > 1 - RAMP:
        return 1 - v * (1 - p) ** 2 / (2 * RAMP)
    return v * (p - RAMP / 2)


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
    home_x: float = 0.0  # this blob's place in the lump
    home_y: float = 0.0
    trip: float = -1.0  # progress round the loop, 0..1; negative while it rests in the lump
    rest_until: float = 0.0  # animation time from which it may leave the lump again
    risen: float = 0.0  # 0 = part of the lump, 1 = out on the loop
    lane: float = 0.0  # sideways offset from the loop, so blobs do not run in single file
    order: int = 0  # left-to-right place in the lump, kept as blobs come and go

    @property
    def resting(self) -> bool:
        return self.trip < 0

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
        # One convection loop, a rounded rectangle whose bottom edge runs through the lump.
        # Which side the lava climbs varies by round.
        self._left, self._right = size.w * LOOP_INSET, size.w * (1 - LOOP_INSET)
        self._top, self._bottom = base_r * 0.9, size.h - base_r * 0.9
        self._rising_left = self.rng.random() < 0.5
        corner = min(self._right - self._left, self._bottom - self._top) * 0.35
        self._corner = max(0.0, corner)
        straight = 2 * (self._right - self._left - 2 * self._corner) + 2 * (self._bottom - self._top - 2 * self._corner)
        self._loop_len = max(1.0, straight + 2 * math.pi * self._corner)
        # The lump: blobs packed shoulder to shoulder at the bottom centre, heaped in the
        # middle so the metaball field reads as one dome rather than a bar.
        cx = size.w / 2
        spread = min(size.w * 0.16, base_r * 0.45 * max(1, n - 1))
        self.blobs = []
        for i in range(n):
            radius = int(base_r * self.rng.uniform(0.7, 1.15))
            u = 0.0 if n == 1 else (i / (n - 1) - 0.5) * 2  # -1 .. 1 across the lump
            hx = min(max(cx + u * spread, radius * 0.3), size.w - radius * 0.3)
            hy = size.h - radius * 0.35 - (1 - abs(u)) * radius * 0.6
            self.blobs.append(
                Blob(
                    x=hx,
                    y=hy,
                    phase=self.rng.uniform(0, 2 * math.pi),
                    rate=self.rng.uniform(0.75, 1.3),
                    wobble=self.rng.uniform(0.3, 0.8),
                    radius=radius,
                    home_x=hx,
                    home_y=hy,
                    lane=self.rng.uniform(-1.0, 1.0) * base_r * 0.4,
                    order=i,
                )
            )
        self._max_travelling = max(1, n - max(1, round(n * RESTING_SHARE)))
        self._lump_x = cx
        self._lump_step = 0.0 if n == 1 else 2 * spread / (n - 1)
        self._lump_half = max(1.0, (n - 1) / 2)
        self._next_departure = WARMUP_DELAY
        self.t = 0.0
        self._lut = self._build_lut()
        self._size = size

    def _loop_pos(self, travelled: float) -> tuple[float, float]:
        """A point on the loop, `travelled` of the way round from the bottom centre.

        Worked out for lava that climbs the left side; a right-climbing lamp is its mirror.
        Arc length is used as the parameter, so the pace is even the whole way round instead
        of crawling up short columns and dashing across long ones.
        """
        left, right, top, bottom, rc = self._left, self._right, self._top, self._bottom, self._corner
        cx = (left + right) / 2
        s = (travelled % 1.0) * self._loop_len
        quarter = math.pi / 2 * rc
        legs: list[tuple[float, tuple[float, float, float, float] | tuple[float, float, float]]] = [
            (cx - left - rc, (cx, bottom, left + rc, bottom)),  # along the floor to the rising side
            (quarter, (left + rc, bottom - rc, math.pi / 2)),  # round the bottom corner
            (bottom - top - 2 * rc, (left, bottom - rc, left, top + rc)),  # up
            (quarter, (left + rc, top + rc, math.pi)),
            (right - left - 2 * rc, (left + rc, top, right - rc, top)),  # across the top
            (quarter, (right - rc, top + rc, 3 * math.pi / 2)),
            (bottom - top - 2 * rc, (right, top + rc, right, bottom - rc)),  # down
            (quarter, (right - rc, bottom - rc, 0.0)),
            (right - rc - cx, (right - rc, bottom, cx, bottom)),  # back along the floor
        ]
        x, y = cx, bottom
        for length, leg in legs:
            if s <= length or leg is legs[-1][1]:
                k = 0.0 if length <= 0 else min(1.0, s / length)
                if len(leg) == 4:
                    x0, y0, x1, y1 = leg
                    x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
                else:
                    ccx, ccy, a0 = leg
                    a = a0 + k * math.pi / 2
                    x, y = ccx + rc * math.cos(a), ccy + rc * math.sin(a)
                break
            s -= length
        if not self._rising_left:
            x = left + right - x
        return x, y

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
        step = dt * self.settings.speed / 30
        self.t += step
        self._maybe_depart()
        self._close_ranks(step, size)
        for b in self.blobs:
            if b.resting:
                # Part of the lump: it only breathes a little in place.
                b.risen = 0.0
                b.x = b.home_x + math.sin(self.t * 0.5 * b.wobble + b.phase) * b.radius * 0.12
                b.y = b.home_y + math.sin(self.t * 0.4 * b.wobble + b.phase * 2) * b.radius * 0.08
                continue
            b.trip += step / LOOP_PERIOD * b.rate
            if b.trip >= 1.0:
                b.trip = -1.0  # back in the lump
                b.rest_until = self.t + self.rng.uniform(*REST)
                b.x, b.y, b.risen = b.home_x, b.home_y, 0.0
                continue
            lx, ly = self._loop_pos(_travelled(b.trip))
            # Near either end of the trip the blob is still (or again) part of the lump, so
            # pull it toward its own place there; away from the ends it follows the loop.
            b.risen = _ease(min(b.trip, 1.0 - b.trip) / JOIN)
            wob = math.sin(self.t * 0.6 * b.wobble + b.phase) * b.radius * 0.45
            lx += (b.lane + wob) * b.risen
            b.x = b.home_x + (lx - b.home_x) * b.risen
            b.y = b.home_y + (ly - b.home_y) * b.risen
            b.x = min(max(b.x, b.radius * 0.3), size.w - b.radius * 0.3)
            b.y = min(max(b.y, b.radius * 0.3), size.h - b.radius * 0.3)

    def _close_ranks(self, step: float, size: Size) -> None:
        """Keep whoever is home packed into one lump at the bottom centre.

        With fixed places, the two blobs left behind when the rest are out on the loop could be
        the two ends of the lump, far enough apart not to merge -- and the lump vanished. Instead
        the blobs at home slide together as others leave, and make room as they come back.
        """
        home = sorted((b for b in self.blobs if b.resting), key=lambda b: b.order)
        middle = (len(home) - 1) / 2
        pull = min(1.0, step * 1.5)
        for k, b in enumerate(home):
            tx = self._lump_x + (k - middle) * self._lump_step
            dome = 1 - abs(k - middle) / self._lump_half
            ty = size.h - b.radius * 0.35 - dome * b.radius * 0.6
            b.home_x += (tx - b.home_x) * pull
            b.home_y += (ty - b.home_y) * pull

    def _maybe_depart(self) -> None:
        """Send one blob out of the lump when it is time, keeping some always at home."""
        if self.t < self._next_departure:
            return
        if sum(not b.resting for b in self.blobs) >= self._max_travelling:
            return
        ready = [b for b in self.blobs if b.resting and b.rest_until <= self.t]
        if not ready:
            return
        blob = self.rng.choice(ready)
        blob.trip = 0.0
        self._next_departure = self.t + self.rng.uniform(*DEPART_GAP)

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
