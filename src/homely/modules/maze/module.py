"""Maze: a thin-walled maze of random size is drawn wall pixel by wall pixel, then the
shortest path from the left-edge entrance to the right-edge exit is traced through the cell
centers, one pixel at a time. Hold, clear, repeat. (After Leah's maze_board prototype.)"""

from __future__ import annotations

import random
from collections import deque
from enum import Enum

from PIL import Image

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.maze.settings import MazeSettings
from homely.render.canvas import Canvas
from homely.render.color import parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

Cell = tuple[int, int]  # (row, col)


class Phase(Enum):
    WALLS = "walls"
    PATH = "path"
    HOLD = "hold"


class Grid:
    """Cells with right/bottom walls; entrance on the left edge, exit on the right edge."""

    def __init__(self, rows: int, cols: int, rng: random.Random) -> None:
        self.rows, self.cols = rows, cols
        self.right = [[True] * cols for _ in range(rows)]
        self.bottom = [[True] * cols for _ in range(rows)]
        self.start_row = rng.randrange(rows)
        self.end_row = rng.randrange(rows)
        self.right[self.end_row][cols - 1] = False  # exit
        self._carve(rng)

    def _carve(self, rng: random.Random) -> None:
        visited = [[False] * self.cols for _ in range(self.rows)]
        stack: list[Cell] = [(self.start_row, 0)]
        visited[self.start_row][0] = True
        while stack:
            r, c = stack[-1]
            moves = [(r - 1, c), (r, c + 1), (r + 1, c), (r, c - 1)]
            rng.shuffle(moves)
            for nr, nc in moves:
                if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr][nc]:
                    visited[nr][nc] = True
                    if nr < r:
                        self.bottom[nr][nc] = False
                    elif nc > c:
                        self.right[r][c] = False
                    elif nr > r:
                        self.bottom[r][c] = False
                    else:
                        self.right[nr][nc] = False
                    stack.append((nr, nc))
                    break
            else:
                stack.pop()

    def open_between(self, a: Cell, b: Cell) -> bool:
        (r1, c1), (r2, c2) = a, b
        if r1 == r2:
            return not self.right[r1][min(c1, c2)]
        return not self.bottom[min(r1, r2)][c1]

    def shortest_path(self) -> list[Cell]:
        start, goal = (self.start_row, 0), (self.end_row, self.cols - 1)
        parent: dict[Cell, Cell] = {}
        seen = {start}
        q: deque[Cell] = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            r, c = cur
            for nxt in ((r, c + 1), (r + 1, c), (r, c - 1), (r - 1, c)):
                if (
                    0 <= nxt[0] < self.rows
                    and 0 <= nxt[1] < self.cols
                    and nxt not in seen
                    and self.open_between(cur, nxt)
                ):
                    seen.add(nxt)
                    parent[nxt] = cur
                    q.append(nxt)
        path = [goal]
        while path[-1] != start:
            path.append(parent[path[-1]])
        path.reverse()
        return path


class MazeModule(Module[MazeSettings]):
    info = ModuleInfo(
        id="maze",
        name="Maze",
        description="Idle animation: a maze is drawn wall by wall, then its solution is traced.",
        tier=Tier.NEED,
        icon="maze",
        default_duration_s=120,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = MazeSettings

    def __init__(self, ctx: ModuleContext, settings: MazeSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._img: Image.Image | None = None
        self._reset(ctx.size)

    # ---- one round ----------------------------------------------------------------------

    def _reset(self, size: Size) -> None:
        w, h = size.w, size.h
        s = self.settings
        max_cols = max(s.min_cells, w // s.min_cell_px)
        max_rows = max(s.min_cells, h // s.min_cell_px)
        cols = self.rng.randint(s.min_cells, max_cols)
        rows = self.rng.randint(s.min_cells, max_rows)
        self.grid = Grid(rows, cols, self.rng)
        self.cell_w, self.cell_h = w // cols, h // rows
        self.ox = (w - cols * self.cell_w) // 2
        self.oy = (h - rows * self.cell_h) // 2
        self._img = Image.new("RGB", (w, h), (0, 0, 0))
        self.wall_pixels = self._wall_pixels()
        self.path_pixels = self._path_pixels(self.grid.shortest_path())
        self._drawn = 0
        self._acc = 0.0
        self._phase = Phase.WALLS
        self._timer = 0.0

    def _wall_pixels(self) -> list[tuple[int, int]]:
        g, cw, ch = self.grid, self.cell_w, self.cell_h
        px: list[tuple[int, int]] = []
        px.extend((x, self.oy) for x in range(self.ox, self.ox + g.cols * cw))  # top border
        for r in range(g.rows):
            for c in range(g.cols):
                x, y = self.ox + c * cw, self.oy + r * ch
                if c == 0 and r != g.start_row:
                    px.extend((self.ox, yy) for yy in range(y, y + ch))
                if g.bottom[r][c]:
                    px.extend((xx, y + ch - 1) for xx in range(x, x + cw))
                if g.right[r][c]:
                    px.extend((x + cw - 1, yy) for yy in range(y, y + ch))
        return px

    def _center(self, cell: Cell) -> tuple[int, int]:
        r, c = cell
        return self.ox + c * self.cell_w + self.cell_w // 2, self.oy + r * self.cell_h + self.cell_h // 2

    def _path_pixels(self, path: list[Cell]) -> list[tuple[int, int]]:
        px: list[tuple[int, int]] = []
        # lead in from the left edge and out through the right edge like the prototype's open walls
        sx, sy = self._center(path[0])
        px.extend((x, sy) for x in range(self.ox, sx))
        for a, b in zip(path, path[1:], strict=False):
            (x1, y1), (x2, y2) = self._center(a), self._center(b)
            dx, dy = x2 - x1, y2 - y1
            dist = max(abs(dx), abs(dy))
            for step in range(dist + 1):
                px.append((int(x1 + dx * step / dist), int(y1 + dy * step / dist)))
        ex, ey = self._center(path[-1])
        px.extend((x, ey) for x in range(ex, self.ox + self.grid.cols * self.cell_w))
        return px

    # ---- animation -------------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        assert self._img is not None
        if self._phase is Phase.WALLS:
            self._acc += dt * self.settings.draw_speed
            n = int(self._acc)
            self._acc -= n
            color = parse_color(self.settings.wall_color)
            end = min(len(self.wall_pixels), self._drawn + n)
            for x, y in self.wall_pixels[self._drawn : end]:
                self._img.putpixel((x, y), color)
            self._drawn = end
            if self._drawn >= len(self.wall_pixels):
                self._phase, self._drawn, self._acc = Phase.PATH, 0, 0.0
        elif self._phase is Phase.PATH:
            self._acc += dt * self.settings.solve_speed
            n = int(self._acc)
            self._acc -= n
            color = parse_color(self.settings.path_color)
            end = min(len(self.path_pixels), self._drawn + n)
            for x, y in self.path_pixels[self._drawn : end]:
                self._img.putpixel((x, y), color)
            self._drawn = end
            if self._drawn >= len(self.path_pixels):
                self._phase, self._timer = Phase.HOLD, 0.0
        else:
            self._timer += dt
            if self._timer >= self.settings.pause_s:
                self._reset(self.ctx.size)

    async def on_settings_changed(self, settings: MazeSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if self._img is None or self._img.size != c.size.as_tuple():
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        assert self._img is not None
        c.blit(self._img, 0, 0)
