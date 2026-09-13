"""Qix: the bouncing bundle of lines from the 1981 arcade game, as an idle animation."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.qix.settings import QixSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, hsv, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size


@dataclass
class Point:
    x: float
    y: float
    vx: float
    vy: float

    def step(self, dt: float, w: int, h: int, rng: random.Random) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x < 0:
            self.x, self.vx = -self.x, abs(self.vx) * rng.uniform(0.8, 1.2)
        elif self.x > w - 1:
            self.x, self.vx = 2 * (w - 1) - self.x, -abs(self.vx) * rng.uniform(0.8, 1.2)
        if self.y < 0:
            self.y, self.vy = -self.y, abs(self.vy) * rng.uniform(0.8, 1.2)
        elif self.y > h - 1:
            self.y, self.vy = 2 * (h - 1) - self.y, -abs(self.vy) * rng.uniform(0.8, 1.2)


@dataclass
class Qix:
    a: Point
    b: Point
    hue: float
    lines: deque[tuple[int, int, int, int, float]]  # x0, y0, x1, y1, hue


class QixModule(Module[QixSettings]):
    info = ModuleInfo(
        id="qix",
        name="Qix",
        description="Idle animation: a bundle of colorful lines drifts and bounces around the panel.",
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
        self._spawn_acc = 0.0
        self._t = 0.0
        self._reset(ctx.size)

    def _reset(self, size: Size) -> None:
        self.qixes = []
        w, h = size.w, size.h
        for i in range(self.settings.qixes):
            speed = float(self.settings.speed)
            a = Point(self.rng.uniform(0, w - 1), self.rng.uniform(0, h - 1), *self._vel(speed))
            b = Point(self.rng.uniform(0, w - 1), self.rng.uniform(0, h - 1), *self._vel(speed))
            self.qixes.append(Qix(a, b, hue=i / max(1, self.settings.qixes), lines=deque(maxlen=self.settings.trail)))
        self._spawn_acc = 0.0

    def _vel(self, speed: float) -> tuple[float, float]:
        ang = self.rng.uniform(0, 6.283185)
        s = speed * self.rng.uniform(0.7, 1.3)
        return math.cos(ang) * s, math.sin(ang) * s

    async def on_settings_changed(self, settings: QixSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def advance(self, dt: float, size: Size) -> None:
        self._t += dt
        for q in self.qixes:
            q.a.step(dt, size.w, size.h, self.rng)
            q.b.step(dt, size.w, size.h, self.rng)
        self._spawn_acc += dt * self.settings.spawn_rate
        while self._spawn_acc >= 1.0:
            self._spawn_acc -= 1.0
            for q in self.qixes:
                hue = (self._t / self.settings.hue_speed + q.hue) % 1.0
                q.lines.append((round(q.a.x), round(q.a.y), round(q.b.x), round(q.b.y), hue))

    def _color(self, hue: float, age: float, index: int) -> Color:
        mode = self.settings.color_mode
        if mode == "rainbow":
            base = hsv(hue)
        elif mode == "duo":
            base = lerp(parse_color(self.settings.color), parse_color(self.settings.color2), (hue * 4) % 1.0)
        else:
            base = parse_color(self.settings.color)
        if index == 0 and mode != "rainbow":
            base = lerp(base, (255, 255, 255), 0.4)
        if self.settings.fade_trail:
            return dim(base, 0.15 + 0.85 * age)
        return base

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if not self.qixes or c.size != self.ctx.size:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25), c.size)
        for q in self.qixes:
            n = len(q.lines)
            for i, (x0, y0, x1, y1, hue) in enumerate(q.lines):
                age = (i + 1) / n  # 1.0 = newest
                c.line(x0, y0, x1, y1, self._color(hue, age, 0 if i == n - 1 else 1))
