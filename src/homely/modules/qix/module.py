"""Qix: a jittery line whose endpoints bounce around the panel with a short fading trail and
a color that wanders. (After Leah's qix_type_beat prototype, which runs at 30 fps.)"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.qix.settings import QixSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, hsv, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

PROTOTYPE_FPS = 30.0


@dataclass
class Qix:
    x1: float
    y1: float
    x2: float
    y2: float
    dx1: int = 1
    dx2: int = 1
    dy1: int = 1
    dy2: int = -1
    r: int = 0
    g: int = 0
    b: int = 0
    hue: float = 0.0
    lines: deque[tuple[int, int, int, int, Color]] = field(default_factory=deque)


class QixModule(Module[QixSettings]):
    info = ModuleInfo(
        id="qix",
        name="Qix",
        description="Idle animation: a jittery, color-shifting line bounces around leaving a short trail.",
        tier=Tier.NEED,
        icon="qix",
        default_duration_s=60,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = QixSettings

    def __init__(self, ctx: ModuleContext, settings: QixSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self.qixes: list[Qix] = []
        self._frame_acc = 0.0
        self._reset(ctx.size)

    def _reset(self, size: Size) -> None:
        rng = self.rng
        self.qixes = []
        for i in range(self.settings.qixes):
            q = Qix(
                x1=rng.randint(0, size.w - 1),
                y1=rng.randint(0, size.h - 1),
                x2=rng.randint(0, size.w - 1),
                y2=rng.randint(0, size.h - 1),
                r=rng.randint(0, 255),
                g=rng.randint(0, 255),
                b=rng.randint(0, 255),
                hue=i / max(1, self.settings.qixes),
                lines=deque(maxlen=self.settings.trail),
            )
            q.lines.append((int(q.x1), int(q.y1), int(q.x2), int(q.y2), self._current_color(q)))
            self.qixes.append(q)

    async def on_settings_changed(self, settings: QixSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    # ---- simulation: one prototype frame -----------------------------------------------------

    def _move(self, value: float, sign: int, limit: int) -> tuple[float, int]:
        rng = self.rng
        value += sign * rng.randint(1, self.settings.jitter) * rng.uniform(1, 3)
        if value >= limit - 1:
            return float(limit - 1), -sign
        if value <= 0:
            return 0.0, -sign
        return value, sign

    def _current_color(self, q: Qix) -> Color:
        mode = self.settings.color_mode
        if mode == "walk":
            return (q.r, q.g, q.b)
        if mode == "rainbow":
            return hsv(q.hue)
        return parse_color(self.settings.color)

    def _step(self, q: Qix, size: Size) -> None:
        q.x1, q.dx1 = self._move(q.x1, q.dx1, size.w)
        q.x2, q.dx2 = self._move(q.x2, q.dx2, size.w)
        q.y1, q.dy1 = self._move(q.y1, q.dy1, size.h)
        q.y2, q.dy2 = self._move(q.y2, q.dy2, size.h)
        step = self.settings.color_step
        q.r = (q.r + self.rng.randint(1, step)) % 256
        q.g = (q.g + self.rng.randint(1, step)) % 256
        q.b = (q.b + self.rng.randint(1, step)) % 256
        q.hue = (q.hue + 0.004) % 1.0
        q.lines.append((int(q.x1), int(q.y1), int(q.x2), int(q.y2), self._current_color(q)))

    def advance(self, dt: float, size: Size) -> None:
        """Run whole prototype frames (30/s) regardless of the real render rate."""
        self._frame_acc += dt * PROTOTYPE_FPS
        steps = int(self._frame_acc)
        self._frame_acc -= steps
        for _ in range(min(steps, 8)):
            for q in self.qixes:
                self._step(q, size)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if not self.qixes or c.size != self.ctx.size:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25), c.size)
        for q in self.qixes:
            n = len(q.lines)
            for i, (x1, y1, x2, y2, color) in enumerate(q.lines):
                shade = dim(color, (i + 1) / n) if self.settings.fade_trail else color
                c.line(x1, y1, x2, y2, shade)
