"""Starfield: fly through space. Stars live in 3D and are projected with the renderer's camera;
nearer stars are brighter and streak. Now and then a shooting star crosses the sky."""

from __future__ import annotations

import random
from dataclasses import dataclass

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.starfield.settings import StarfieldSettings
from homely.render.canvas import Canvas
from homely.render.color import WHITE, Color, dim, hsv, lerp
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.three import Camera

FAR = 40.0
SPREAD = 20.0


@dataclass
class Star:
    x: float
    y: float
    z: float
    color: Color
    prev: tuple[int, int] | None = None


@dataclass
class Shooter:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: Color


class StarfieldModule(Module[StarfieldSettings]):
    info = ModuleInfo(
        id="starfield",
        name="Starfield",
        description="Idle animation: fly through a 3D field of stars, with the odd shooting star.",
        tier=Tier.NEED,
        icon="starfield",
        default_duration_s=60,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = StarfieldSettings

    def __init__(self, ctx: ModuleContext, settings: StarfieldSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self.stars: list[Star] = []
        self.shooters: list[Shooter] = []
        self._next_shooter = self.rng.uniform(2, 6)
        self._reset(ctx.size)

    def _star_color(self) -> Color:
        mode = self.settings.color_mode
        if mode == "white":
            return WHITE
        if mode == "rainbow":
            return hsv(self.rng.random(), 0.7, 1.0)
        return lerp(WHITE, hsv(self.rng.random(), 1.0, 1.0), self.rng.uniform(0.0, 0.35))

    def _spawn(self, z: float | None = None) -> Star:
        return Star(
            x=self.rng.uniform(-SPREAD, SPREAD),
            y=self.rng.uniform(-SPREAD, SPREAD),
            z=z if z is not None else self.rng.uniform(1.0, FAR),
            color=self._star_color(),
        )

    def _reset(self, size: Size) -> None:
        self.cam = Camera(size.w, size.h, focal=min(size.w, size.h) * 0.9)
        self.stars = [self._spawn() for _ in range(self.settings.stars)]
        self.shooters = []

    async def on_settings_changed(self, settings: StarfieldSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def advance(self, dt: float, size: Size) -> None:
        dz = self.settings.speed * dt * 0.25
        for s in self.stars:
            s.z -= dz
            if s.z <= self.cam.near:
                fresh = self._spawn(FAR)
                s.x, s.y, s.z, s.color, s.prev = fresh.x, fresh.y, fresh.z, fresh.color, None
        if self.settings.shooting_stars:
            self._next_shooter -= dt
            if self._next_shooter <= 0:
                self._next_shooter = self.rng.uniform(4, 12)
                edge_y = self.rng.uniform(0, size.h * 0.6)
                going_right = self.rng.random() < 0.5
                self.shooters.append(
                    Shooter(
                        x=-2.0 if going_right else size.w + 2.0,
                        y=edge_y,
                        vx=(size.w * 1.5) * (1 if going_right else -1),
                        vy=size.h * self.rng.uniform(0.2, 0.6),
                        life=1.0,
                        color=lerp(WHITE, (255, 230, 150), 0.5),
                    )
                )
        for sh in self.shooters:
            sh.x += sh.vx * dt
            sh.y += sh.vy * dt
            sh.life -= dt * 0.9
        self.shooters = [sh for sh in self.shooters if sh.life > 0 and -8 <= sh.x <= size.w + 8]

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if c.size != self.ctx.size or self.cam.width != c.width:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25), c.size)
        for s in self.stars:
            p = self.cam.project((s.x, s.y, s.z))
            if p is None:
                continue
            x, y = round(p[0]), round(p[1])
            if not (0 <= x < c.width and 0 <= y < c.height):
                s.prev = None
                continue
            k = max(0.08, 1.0 - s.z / FAR) ** 1.5
            col = dim(s.color, k)
            if (
                self.settings.trails
                and s.prev is not None
                and (abs(s.prev[0] - x) + abs(s.prev[1] - y)) <= max(c.width, c.height) // 4
            ):
                c.line(s.prev[0], s.prev[1], x, y, dim(col, 0.5))
            c.pixel(x, y, col)
            if s.z < FAR * 0.12 and c.width >= 48:  # the closest stars grow to 2x2
                c.pixel(x + 1, y, dim(col, 0.6))
                c.pixel(x, y + 1, dim(col, 0.6))
            s.prev = (x, y)
        for sh in self.shooters:
            tail_x = sh.x - sh.vx * 0.06
            tail_y = sh.y - sh.vy * 0.06
            c.line(round(tail_x), round(tail_y), round(sh.x), round(sh.y), dim(sh.color, 0.5 * sh.life))
            c.pixel(round(sh.x), round(sh.y), dim(sh.color, sh.life))
