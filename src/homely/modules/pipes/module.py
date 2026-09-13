"""Pipes: the classic screensaver in 3D. Pipes grow through a voxel grid with random turns,
rendered as shaded square tubes into a persistent frame with a depth buffer, so each frame only
draws the newest piece and earlier pipes correctly hide behind later ones."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from PIL import Image

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.pipes.settings import PipesSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, hsv
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.three import (
    Camera,
    DepthBuffer,
    Vec3,
    m_apply,
    m_mul,
    m_rot_x,
    m_rot_y,
    m_translate,
    shade,
    v_add,
    v_cross,
    v_norm,
    v_scale,
    v_sub,
)

Voxel = tuple[int, int, int]
AXES: tuple[Voxel, ...] = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
LIGHT: Vec3 = (-0.5, 0.9, -0.7)
PALETTES: dict[str, list[Color]] = {
    "classic": [(230, 60, 60), (60, 200, 80), (70, 120, 255), (250, 210, 40), (220, 80, 220), (60, 210, 220)],
    "warm": [(255, 90, 40), (255, 160, 40), (250, 220, 60), (230, 70, 110), (255, 120, 90), (200, 80, 40)],
    "cool": [(60, 120, 255), (60, 210, 220), (120, 90, 255), (60, 200, 150), (100, 160, 255), (180, 120, 255)],
    "mono": [(220, 220, 230)],
}


class Phase(Enum):
    GROW = "grow"
    HOLD = "hold"
    FADE = "fade"


@dataclass
class Pipe:
    pos: Voxel
    direction: Voxel
    color: Color
    length: int = 0


class PipesModule(Module[PipesSettings]):
    info = ModuleInfo(
        id="pipes",
        name="Pipes",
        description="Idle animation: the classic 3D pipes screensaver, tube by tube.",
        tier=Tier.NEED,
        icon="pipes",
        default_duration_s=90,
        default_fps=30,
        min_size=Size(32, 32),
    )
    Settings = PipesSettings

    def __init__(self, ctx: ModuleContext, settings: PipesSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._img: Image.Image | None = None
        self._reset(ctx.size)

    # ---- round setup ---------------------------------------------------------------------

    def _reset(self, size: Size) -> None:
        n = self.settings.grid
        self.n = n
        self.occupied: set[Voxel] = set()
        self.cam = Camera(size.w, size.h, focal=min(size.w, size.h) * 1.3)
        # A slightly turned, slightly tilted view of the cube, sized to fill the panel.
        self.view = m_mul(m_translate(0, 0, 3.6), m_mul(m_rot_x(-0.42), m_rot_y(0.62)))
        self.cell = 2.0 / n  # cube spans [-1, 1]
        self.radius = self.cell * 0.22
        self._img = Image.new("RGB", (size.w, size.h), (0, 0, 0))
        self._canvas = Canvas(size, image=self._img)
        self.depth = DepthBuffer(size.w, size.h)
        self.pipe: Pipe | None = None
        self.done_pipes = 0
        self.progress = 0.0  # fraction of the current segment already drawn
        self._phase = Phase.GROW
        self._timer = 0.0
        self._colors = list(PALETTES[self.settings.palette])
        self.rng.shuffle(self._colors)
        self._start_pipe()

    def _free(self, v: Voxel) -> bool:
        return all(0 <= c < self.n for c in v) and v not in self.occupied

    def _start_pipe(self) -> None:
        free = [
            (x, y, z)
            for x in range(self.n)
            for y in range(self.n)
            for z in range(self.n)
            if (x, y, z) not in self.occupied
        ]
        if not free or self.done_pipes >= self.settings.pipes:
            self.pipe = None
            self._phase = Phase.HOLD
            self._timer = 0.0
            return
        pos = self.rng.choice(free)
        color = self._colors[self.done_pipes % len(self._colors)]
        if self.settings.palette == "mono":
            color = hsv(self.rng.random(), 0.25, 0.9)
        self.pipe = Pipe(pos=pos, direction=self.rng.choice(AXES), color=color)
        self.occupied.add(pos)
        self._draw_joint(pos, color)
        self.progress = 0.0
        if not self._pick_direction():
            self._finish_pipe()

    def _pick_direction(self) -> bool:
        assert self.pipe is not None
        p = self.pipe
        ahead = (p.pos[0] + p.direction[0], p.pos[1] + p.direction[1], p.pos[2] + p.direction[2])
        turn = self.rng.random() * 100 < self.settings.turn_chance or not self._free(ahead)
        options = [d for d in AXES if self._free((p.pos[0] + d[0], p.pos[1] + d[1], p.pos[2] + d[2]))]
        if not options:
            return False
        if turn:
            turns = [d for d in options if d != p.direction and d != tuple(-c for c in p.direction)]
            if turns:
                new_dir = self.rng.choice(turns)
                if new_dir != p.direction and self.settings.joints and p.length:
                    self._draw_joint(p.pos, p.color)
                p.direction = new_dir
            else:
                p.direction = self.rng.choice(options)
        return True

    def _finish_pipe(self) -> None:
        if self.pipe is not None and self.settings.joints:
            self._draw_joint(self.pipe.pos, self.pipe.color)
        self.done_pipes += 1
        self._start_pipe()

    # ---- geometry ------------------------------------------------------------------------

    def _center(self, v: Voxel) -> Vec3:
        return tuple(-1 + self.cell * (c + 0.5) for c in v)  # type: ignore[return-value]

    def _quad(self, corners: list[Vec3], color: Color) -> None:
        world = [m_apply(self.view, c) for c in corners]
        pts = [self.cam.project(w) for w in world]
        if any(p is None for p in pts):
            return
        normal = v_cross(v_sub(world[1], world[0]), v_sub(world[2], world[0]))
        if normal[0] * world[0][0] + normal[1] * world[0][1] + normal[2] * world[0][2] > 0:
            return  # back face
        self.depth.fill_polygon(self._canvas, pts, shade(color, normal, LIGHT, ambient=0.3))  # type: ignore[arg-type]

    def _tube(self, a: Vec3, b: Vec3, color: Color, radius: float) -> None:
        """Square tube from a to b (world/model space, before the view transform)."""
        axis = v_norm(v_sub(b, a))
        up: Vec3 = (0, 1, 0) if abs(axis[1]) < 0.9 else (1, 0, 0)
        u = v_norm(v_cross(axis, up))
        v = v_norm(v_cross(axis, u))
        offs = [v_scale(u, radius), v_scale(v, radius), v_scale(u, -radius), v_scale(v, -radius)]
        for i in range(4):
            o1, o2 = offs[i], offs[(i + 1) % 4]
            self._quad([v_add(a, o1), v_add(a, o2), v_add(b, o2), v_add(b, o1)], color)

    def _draw_joint(self, v: Voxel, color: Color) -> None:
        c = self._center(v)
        r = self.radius * 1.35
        # a small cube stands in for the ball joint
        corners = [(c[0] + sx * r, c[1] + sy * r, c[2] + sz * r) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (1, 3, 7, 5), (0, 4, 6, 2)]
        for f in faces:
            self._quad([corners[i] for i in f], color)

    # ---- animation -------------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        if self._phase is Phase.GROW:
            if self.pipe is None:
                return
            p = self.pipe
            step = self.settings.speed * dt
            while step > 0 and self.pipe is not None:
                take = min(step, 1.0 - self.progress)
                a = self._center(p.pos)
                nxt = (p.pos[0] + p.direction[0], p.pos[1] + p.direction[1], p.pos[2] + p.direction[2])
                b = self._center(nxt)
                t0, t1 = self.progress, self.progress + take
                pa = v_add(a, v_scale(v_sub(b, a), t0))
                pb = v_add(a, v_scale(v_sub(b, a), t1))
                self._tube(pa, pb, p.color, self.radius)
                self.progress = t1
                step -= take
                if self.progress >= 1.0 - 1e-9:
                    p.pos = nxt
                    p.length += 1
                    self.occupied.add(nxt)
                    self.progress = 0.0
                    if not self._pick_direction():
                        self._finish_pipe()
                        break
        elif self._phase is Phase.HOLD:
            self._timer += dt
            if self._timer >= self.settings.pause_s:
                self._phase, self._timer = Phase.FADE, 0.0
        else:
            self._timer += dt
            if self._timer >= 1.0:
                self._reset(self.ctx.size)

    async def on_settings_changed(self, settings: PipesSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if self._img is None or self._img.size != c.size.as_tuple():
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        assert self._img is not None
        if self._phase is Phase.FADE:
            k = max(0.0, 1.0 - self._timer)
            c.blit(self._img.point(lambda v: int(v * k)), 0, 0)
        else:
            c.blit(self._img, 0, 0)
