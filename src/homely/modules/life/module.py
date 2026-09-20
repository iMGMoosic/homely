"""Conway's Game of Life, computed with Pillow image ops (a 3x3 kernel counts neighbors) so a
128x128 board steps in well under a millisecond. Newborn cells flash white and settle into the
cell color; dying cells leave a fading ghost. When the soup stalls it fades out and reseeds."""

from __future__ import annotations

import random
from collections import deque

from PIL import Image, ImageChops, ImageFilter

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.life.settings import LifeSettings
from homely.render.canvas import Canvas
from homely.render.color import WHITE, Color, hsv, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

_KERNEL = ImageFilter.Kernel((3, 3), [1, 1, 1, 1, 0, 1, 1, 1, 1], scale=1, offset=0)
# lookup on (neighbors * 2 + alive): survive with 2 or 3 neighbors, born with exactly 3
_RULE = bytes(1 if ((v & 1) and (v >> 1) in (2, 3)) or (not (v & 1) and (v >> 1) == 3) else 0 for v in range(256))
_TO_255 = bytes(255 if v else 0 for v in range(256))
TRAIL_DECAY = 28


class LifeModule(Module[LifeSettings]):
    info = ModuleInfo(
        id="life",
        name="Game of Life",
        description="Idle animation: Conway's Game of Life with glowing newborns and fading ghosts.",
        tier=Tier.NEED,
        icon="life",
        default_duration_s=90,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = LifeSettings

    def __init__(self, ctx: ModuleContext, settings: LifeSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._reset(ctx.size)

    # ---- board -----------------------------------------------------------------------------

    def _cell_px(self, size: Size) -> int:
        if self.settings.cell_px:
            return self.settings.cell_px
        return 2 if min(size.w, size.h) >= 96 else 1

    def _reset(self, size: Size) -> None:
        self.px = self._cell_px(size)
        self.cols, self.rows = max(4, size.w // self.px), max(4, size.h // self.px)
        n = self.cols * self.rows
        threshold = self.settings.density / 100
        self.alive = Image.frombytes(
            "L", (self.cols, self.rows), bytes(1 if self.rng.random() < threshold else 0 for _ in range(n))
        )
        self.age = Image.new("L", (self.cols, self.rows), 0)
        self.heat = Image.new("L", (self.cols, self.rows), 0)
        self.generation = 0
        self._acc = 0.0
        self._history: deque[int] = deque(maxlen=12)
        self._stalled_for = 0
        self._fade = 1.0
        self._hue = self.rng.random()

    def _padded(self) -> Image.Image:
        """Board with a one-cell border: copies of the far edges (wrap) or dead cells."""
        w, h = self.alive.size
        pad = Image.new("L", (w + 2, h + 2), 0)
        pad.paste(self.alive, (1, 1))
        if self.settings.wrap:
            pad.paste(self.alive.crop((0, h - 1, w, h)), (1, 0))  # bottom row above the top
            pad.paste(self.alive.crop((0, 0, w, 1)), (1, h + 1))
            pad.paste(self.alive.crop((w - 1, 0, w, h)), (0, 1))
            pad.paste(self.alive.crop((0, 0, 1, h)), (w + 1, 1))
            pad.paste(self.alive.crop((w - 1, h - 1, w, h)), (0, 0))
            pad.paste(self.alive.crop((0, h - 1, 1, h)), (w + 1, 0))
            pad.paste(self.alive.crop((w - 1, 0, w, 1)), (0, h + 1))
            pad.paste(self.alive.crop((0, 0, 1, 1)), (w + 1, h + 1))
        return pad

    def step(self) -> None:
        w, h = self.alive.size
        counts = self._padded().filter(_KERNEL).crop((1, 1, w + 1, h + 1))
        coded = ImageChops.add(counts.point(lambda v: v * 2), self.alive)
        new_alive = coded.point(_RULE)
        died = ImageChops.subtract(self.alive, new_alive)  # 1 where a cell just died
        self.heat = ImageChops.lighter(self.heat.point(lambda v: max(0, v - TRAIL_DECAY)), died.point(_TO_255))
        self.age = ImageChops.multiply(
            ImageChops.add(self.age, new_alive.point(lambda v: 1 if v else 0)), new_alive.point(_TO_255)
        )
        self.alive = new_alive
        self.generation += 1
        digest = hash(self.alive.tobytes())
        if digest in self._history:
            self._stalled_for += 1
        else:
            self._stalled_for = 0
        self._history.append(digest)

    @property
    def population(self) -> int:
        return sum(self.alive.histogram()[1:])

    # ---- animation -------------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        if self._fade < 1.0:
            self._fade = min(1.0, self._fade + dt)  # fade the fresh soup in
        self._acc += dt * self.settings.generations_per_second
        steps = int(self._acc)
        self._acc -= steps
        for _ in range(min(steps, 4)):
            self.step()
            if self._stalled_for >= self.settings.stall_generations or self.population == 0:
                self._reset(self.ctx.size)
                self._fade = 0.0
                break

    async def on_settings_changed(self, settings: LifeSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def on_enter(self) -> None:
        self._reset(self.ctx.size)

    def _palette(self) -> tuple[bytes, bytes, bytes]:
        """RGB lookups indexed by age (0 = dead) for the current color mode."""
        base = hsv(self._hue, 0.8, 1.0) if self.settings.color_mode == "rainbow" else parse_color(self.settings.color)
        rs, gs, bs = bytearray(256), bytearray(256), bytearray(256)
        for age in range(1, 256):
            if self.settings.color_mode == "age":
                col: Color = lerp(WHITE, base, min(1.0, age / 6))
            elif self.settings.color_mode == "rainbow":
                col = hsv((self._hue + age / 40) % 1.0, 0.8, 1.0)
            else:
                col = base
            rs[age], gs[age], bs[age] = col
        return bytes(rs), bytes(gs), bytes(bs)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if self._cell_px(c.size) != self.px or (self.cols * self.px > c.width) or (self.rows * self.px > c.height):
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        rs, gs, bs = self._palette()
        rgb = Image.merge("RGB", (self.age.point(rs), self.age.point(gs), self.age.point(bs)))
        if self.settings.trails:
            ghost = parse_color(self.settings.color)
            trail = Image.merge(
                "RGB",
                tuple(self.heat.point(lambda v, ch=ch: int(v * ch / 255 * 0.35)) for ch in ghost),
            )
            rgb = ImageChops.lighter(rgb, trail)
        if self._fade < 1.0:
            rgb = rgb.point(lambda v: int(v * self._fade))
        if self.px > 1:
            rgb = rgb.resize((self.cols * self.px, self.rows * self.px), Image.Resampling.NEAREST)
        c.blit(rgb, (c.width - rgb.width) // 2, (c.height - rgb.height) // 2)
