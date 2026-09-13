"""Maze: builds a maze with a recursive backtracker, then a little solver walks it.

The animation is a state machine advanced by ``frame.dt``:
BUILD (carve cells) -> SOLVE (depth-first walker with backtracking) -> SHOW (path lit) -> FADE -> new maze.
"""

from __future__ import annotations

import random
from enum import Enum

from PIL import Image

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.maze.settings import MazeSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, hsv, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

Cell = tuple[int, int]
DIRS: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
FADE_S = 1.0


class Phase(Enum):
    BUILD = "build"
    SOLVE = "solve"
    SHOW = "show"
    FADE = "fade"


class MazeModule(Module[MazeSettings]):
    info = ModuleInfo(
        id="maze",
        name="Maze",
        description="Idle animation: a maze grows, then a solver finds its way through.",
        tier=Tier.NEED,
        icon="maze",
        default_duration_s=90,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = MazeSettings

    def __init__(self, ctx: ModuleContext, settings: MazeSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._phase = Phase.BUILD
        self._img: Image.Image | None = None  # walls + corridors, drawn incrementally
        self._reset(ctx.size)

    # ---- geometry -------------------------------------------------------------------------

    def _reset(self, size: Size) -> None:
        cw = self.settings.corridor
        self.pitch = cw + 1
        self.cols = max(2, (size.w - 1) // self.pitch)
        self.rows = max(2, (size.h - 1) // self.pitch)
        grid_w = self.cols * self.pitch + 1
        grid_h = self.rows * self.pitch + 1
        self.ox = (size.w - grid_w) // 2
        self.oy = (size.h - grid_h) // 2
        self._img = Image.new("RGB", (size.w, size.h), (0, 0, 0))
        self._canvas = Canvas(size, image=self._img)
        # Fill the grid area with walls; carving removes them.
        self._canvas.rect(self.ox, self.oy, grid_w, grid_h, fill=self._wall_color(0.0))
        self.visited: set[Cell] = set()
        self.open: set[tuple[Cell, Cell]] = set()  # carved passages (a, b) both orders
        self.stack: list[Cell] = [(0, 0)]
        self.visited.add((0, 0))
        self._carve_cell((0, 0), 0.0)
        self.total = self.cols * self.rows
        self._acc = 0.0
        self._phase = Phase.BUILD
        self.start: Cell = (0, 0)
        self.goal: Cell = (self.cols - 1, self.rows - 1)
        self.path: list[Cell] = []
        self.dead: set[Cell] = set()
        self.solved = False
        self._timer = 0.0

    def _wall_color(self, progress: float) -> Color:
        if self.settings.rainbow_walls:
            return dim(hsv(progress * 0.8), 0.8)
        return parse_color(self.settings.wall_color)

    def _cell_px(self, cell: Cell) -> tuple[int, int]:
        return self.ox + 1 + cell[0] * self.pitch, self.oy + 1 + cell[1] * self.pitch

    def _carve_cell(self, cell: Cell, progress: float) -> None:
        x, y = self._cell_px(cell)
        cw = self.settings.corridor
        self._canvas.rect(x, y, cw, cw, fill=(0, 0, 0))
        if self.settings.rainbow_walls:
            # tint the walls around a freshly carved cell so the rainbow reflects build order
            col = self._wall_color(progress)
            for dx, dy in DIRS:
                nx, ny = cell[0] + dx, cell[1] + dy
                wx, wy = self._wall_px(cell, (nx, ny))
                if (cell, (nx, ny)) not in self.open:
                    self._canvas.rect(wx, wy, cw if dx == 0 else 1, cw if dy == 0 else 1, fill=col)

    def _wall_px(self, a: Cell, b: Cell) -> tuple[int, int]:
        """Top-left pixel of the wall segment between adjacent cells a and b."""
        ax, ay = self._cell_px(a)
        cw = self.settings.corridor
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == 1:
            return ax + cw, ay
        if dx == -1:
            return ax - 1, ay
        if dy == 1:
            return ax, ay + cw
        return ax, ay - 1

    def _carve_between(self, a: Cell, b: Cell) -> None:
        cw = self.settings.corridor
        wx, wy = self._wall_px(a, b)
        horizontal = a[1] == b[1]
        self._canvas.rect(wx, wy, 1 if horizontal else cw, cw if horizontal else 1, fill=(0, 0, 0))
        self.open.add((a, b))
        self.open.add((b, a))

    def _neighbors(self, cell: Cell) -> list[Cell]:
        out = []
        for dx, dy in DIRS:
            n = (cell[0] + dx, cell[1] + dy)
            if 0 <= n[0] < self.cols and 0 <= n[1] < self.rows:
                out.append(n)
        return out

    # ---- simulation --------------------------------------------------------------------------

    def _build_steps(self, n: int) -> None:
        for _ in range(n):
            if not self.stack:
                self._phase = Phase.SOLVE
                self.path = [self.start]
                self.dead = set()
                return
            cur = self.stack[-1]
            options = [c for c in self._neighbors(cur) if c not in self.visited]
            if not options:
                self.stack.pop()
                continue
            nxt = self.rng.choice(options)
            self.visited.add(nxt)
            self._carve_between(cur, nxt)
            self._carve_cell(nxt, len(self.visited) / self.total)
            self.stack.append(nxt)

    def _solve_steps(self, n: int) -> None:
        for _ in range(n):
            if not self.path:
                self._phase = Phase.SHOW
                return
            cur = self.path[-1]
            if cur == self.goal:
                self.solved = True
                self._phase = Phase.SHOW
                self._timer = 0.0
                return
            options = [
                c
                for c in self._neighbors(cur)
                if (cur, c) in self.open and c not in self.dead and (len(self.path) < 2 or c != self.path[-2])
            ]
            options = [c for c in options if c not in self.path]
            if options:
                # prefer moving toward the goal a little, but stay random enough to be fun
                options.sort(key=lambda c: abs(c[0] - self.goal[0]) + abs(c[1] - self.goal[1]) + self.rng.random() * 3)
                self.path.append(options[0])
            else:
                self.dead.add(self.path.pop())

    def advance(self, dt: float) -> None:
        if self._phase is Phase.BUILD:
            self._acc += dt * self.settings.build_speed
            n = int(self._acc)
            self._acc -= n
            self._build_steps(n)
        elif self._phase is Phase.SOLVE:
            self._acc += dt * self.settings.solve_speed
            n = int(self._acc)
            self._acc -= n
            self._solve_steps(n)
        elif self._phase is Phase.SHOW:
            self._timer += dt
            if self._timer >= self.settings.pause_s:
                self._phase = Phase.FADE
                self._timer = 0.0
        elif self._phase is Phase.FADE:
            self._timer += dt
            if self._timer >= FADE_S:
                self._reset(self.ctx.size)

    # ---- render ----------------------------------------------------------------------------

    async def on_settings_changed(self, settings: MazeSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def on_enter(self) -> None:
        if self._phase is Phase.FADE:
            self._reset(self.ctx.size)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if c.size != self.ctx.size or self._img is None:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        assert self._img is not None
        c.blit(self._img, 0, 0)
        cw = self.settings.corridor
        trail = parse_color(self.settings.trail_color)
        explore = parse_color(self.settings.explore_color)
        path_col = parse_color(self.settings.path_color)
        fade = 1.0
        if self._phase is Phase.FADE:
            fade = max(0.0, 1.0 - self._timer / FADE_S)
        # start and goal markers
        for cell, col in ((self.start, dim(path_col, 0.6)), (self.goal, (255, 60, 60))):
            x, y = self._cell_px(cell)
            c.rect(x, y, cw, cw, fill=col)
        if self._phase in (Phase.SOLVE, Phase.SHOW, Phase.FADE):
            for cell in self.dead:
                x, y = self._cell_px(cell)
                c.rect(x, y, cw, cw, fill=dim(explore, fade))
            col = path_col if self.solved else trail
            for i, cell in enumerate(self.path):
                x, y = self._cell_px(cell)
                c.rect(x, y, cw, cw, fill=dim(col, fade))
                if i:
                    # fill the passage between consecutive path cells so the trail is continuous
                    prev = self.path[i - 1]
                    wx, wy = self._wall_px(prev, cell)
                    horizontal = prev[1] == cell[1]
                    c.rect(wx, wy, 1 if horizontal else cw, cw if horizontal else 1, fill=dim(col, fade))
            if self.path and not self.solved:
                hx, hy = self._cell_px(self.path[-1])
                c.rect(hx, hy, cw, cw, fill=lerp(trail, (255, 255, 255), 0.6))
        if self._phase is Phase.FADE and fade < 1.0:
            # dim everything uniformly for the fade-out
            c.image.paste(c.image.point(lambda v: int(v * fade)))
