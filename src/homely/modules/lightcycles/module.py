"""Light cycles: riders race across the arena leaving solid light walls behind them. Each
rider steers by how much open room a move leaves (a bounded flood fill), swerving late when a
wall is close. Crashing derezzes a trail; the last rider standing wins the round."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.lightcycles.settings import LightCyclesSettings
from homely.render.canvas import Canvas
from homely.render.color import WHITE, Color, dim, lerp
from homely.render.layout import layout_fallback
from homely.render.size import Size

Cell = tuple[int, int]
DIRS: tuple[Cell, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))  # right, down, left, up
PALETTES: dict[str, list[Color]] = {
    "classic": [(80, 200, 255), (255, 140, 30), (255, 240, 120), (220, 60, 60)],
    "neon": [(0, 255, 180), (255, 0, 200), (255, 255, 0), (120, 80, 255)],
    "duel": [(60, 160, 255), (255, 60, 40), (60, 160, 255), (255, 60, 40)],
}
FLOOD_CAP = 220


class Phase(Enum):
    RACE = "race"
    OVER = "over"


@dataclass
class Rider:
    pos: Cell
    direction: int  # index into DIRS
    color: Color
    alive: bool = True
    trail: list[Cell] = field(default_factory=list)
    derezz: float = 0.0  # seconds since crash


class LightCyclesModule(Module[LightCyclesSettings]):
    info = ModuleInfo(
        id="lightcycles",
        name="Light cycles",
        description="Idle animation: light cycles duel in the arena, leaving walls of light behind them.",
        tier=Tier.NEED,
        icon="lightcycles",
        default_duration_s=90,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = LightCyclesSettings

    def __init__(self, ctx: ModuleContext, settings: LightCyclesSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._reset(ctx.size)

    # ---- arena -----------------------------------------------------------------------------

    def _cell_px(self, size: Size) -> int:
        if self.settings.cell_px:
            return self.settings.cell_px
        return 2 if min(size.w, size.h) >= 96 else 1

    def _reset(self, size: Size) -> None:
        self.px = self._cell_px(size)
        self.cols, self.rows = max(8, size.w // self.px), max(8, size.h // self.px)
        self.ox, self.oy = (size.w - self.cols * self.px) // 2, (size.h - self.rows * self.px) // 2
        self.walls: dict[Cell, int] = {}  # cell -> rider index
        colors = PALETTES[self.settings.palette]
        n = self.settings.cycles
        # Pinwheel starts: each rider begins near an edge heading along it, so nobody faces
        # another rider at the start (the old layout sent pairs straight into each other).
        cx, cy = self.cols // 2, self.rows // 2
        mx, my = self.cols // 6, self.rows // 6
        starts = [
            ((mx, cy), 3),  # left edge, heading up
            ((self.cols - 1 - mx, cy), 1),  # right edge, heading down
            ((cx, my), 0),  # top edge, heading right
            ((cx, self.rows - 1 - my), 2),  # bottom edge, heading left
        ]
        self.riders: list[Rider] = []
        for i in range(n):
            pos, d = starts[i]
            r = Rider(pos=pos, direction=d, color=colors[i % len(colors)])
            r.trail.append(pos)
            self.walls[pos] = i
            self.riders.append(r)
        self._acc = 0.0
        self._phase = Phase.RACE
        self._timer = 0.0
        self.winner: int | None = None

    def _free(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self.cols and 0 <= cell[1] < self.rows and cell not in self.walls

    def _open_room(self, start: Cell) -> int:
        """Bounded flood fill: how many free cells are reachable from start (capped)."""
        if not self._free(start):
            return 0
        seen = {start}
        q: deque[Cell] = deque([start])
        while q and len(seen) < FLOOD_CAP:
            x, y = q.popleft()
            for dx, dy in DIRS:
                nxt = (x + dx, y + dy)
                if nxt not in seen and self._free(nxt):
                    seen.add(nxt)
                    q.append(nxt)
        return len(seen)

    def _danger(self, me: Rider) -> set[Cell]:
        """Cells the other riders' heads are about to claim: their next few cells ahead."""
        cells: set[Cell] = set()
        for other in self.riders:
            if other is me or not other.alive:
                continue
            x, y = other.pos
            dx, dy = DIRS[other.direction]
            for k in range(1, 4):
                cells.add((x + dx * k, y + dy * k))
            # they might also turn: the cells beside their head next step
            for d in ((other.direction + 1) % 4, (other.direction - 1) % 4):
                cells.add((x + DIRS[d][0], y + DIRS[d][1]))
        return cells

    def _clear_ahead(self, pos: Cell, d: int, danger: set[Cell] | None = None) -> int:
        dx, dy = DIRS[d]
        n = 0
        x, y = pos
        while n < self.settings.lookahead:
            x, y = x + dx, y + dy
            if not self._free((x, y)) or (danger is not None and (x, y) in danger):
                break
            n += 1
        return n

    def _choose(self, r: Rider) -> int | None:
        options = [r.direction, (r.direction + 1) % 4, (r.direction - 1) % 4]
        danger = self._danger(r)
        # Keep going straight while the road ahead is clear; swerve when a wall or rider gets close.
        if self._clear_ahead(r.pos, r.direction, danger) >= self.settings.lookahead and self.rng.random() > 0.04:
            return r.direction
        scored: list[tuple[float, int]] = []
        for d in options:
            nxt = (r.pos[0] + DIRS[d][0], r.pos[1] + DIRS[d][1])
            if not self._free(nxt):
                continue
            room = self._open_room(nxt)
            ahead = self._clear_ahead(r.pos, d, danger)
            score = room + ahead * 2 + (3 if d == r.direction else 0) + self.rng.random() * 2
            if nxt in danger:
                score -= 150  # only if nothing else is left
            scored.append((score, d))
        if not scored:
            return None
        scored.sort(reverse=True)
        return scored[0][1]

    def step(self) -> bool:
        """Advance every living rider one cell; returns False when the round just ended."""
        alive = [i for i, r in enumerate(self.riders) if r.alive]
        moves: dict[int, Cell] = {}
        for i in alive:
            r = self.riders[i]
            d = self._choose(r)
            if d is None:
                r.alive = False
                continue
            r.direction = d
            moves[i] = (r.pos[0] + DIRS[d][0], r.pos[1] + DIRS[d][1])
        # head-on into the same cell: both crash
        targets = list(moves.values())
        for i, cell in moves.items():
            r = self.riders[i]
            if targets.count(cell) > 1 or not self._free(cell):
                r.alive = False
                continue
            r.pos = cell
            r.trail.append(cell)
            self.walls[cell] = i
        still = [i for i, r in enumerate(self.riders) if r.alive]
        if len(still) <= 1:
            self._phase, self._timer = Phase.OVER, 0.0
            self.winner = still[0] if still else None
            return False
        return True

    # ---- animation ---------------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        for r in self.riders:
            if not r.alive:
                r.derezz += dt
        if self._phase is Phase.RACE:
            self._acc += dt * self.settings.speed
            steps = int(self._acc)
            self._acc -= steps
            for _ in range(min(steps, 8)):
                if not self.step():
                    break
        else:
            self._timer += dt
            if self._timer >= self.settings.pause_s:
                self._reset(self.ctx.size)

    async def on_settings_changed(self, settings: LightCyclesSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def _cell(self, c: Canvas, cell: Cell, color: Color) -> None:
        c.rect(self.ox + cell[0] * self.px, self.oy + cell[1] * self.px, self.px, self.px, fill=color)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if self._cell_px(c.size) != self.px or self.cols * self.px > c.width or self.rows * self.px > c.height:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        if self.settings.grid_glow:
            pitch = max(8, min(c.width, c.height) // 8)
            g = (10, 14, 22)
            for x in range(0, c.width, pitch):
                c.vline(x, 0, c.height, g)
            for y in range(0, c.height, pitch):
                c.hline(0, y, c.width, g)
        for i, r in enumerate(self.riders):
            if not r.alive:
                # derezz: the trail breaks into flickering fragments and fades out
                k = max(0.0, 1.0 - r.derezz / 1.2)
                if k <= 0:
                    continue
                for j, cell in enumerate(r.trail):
                    if (j * 7 + int(r.derezz * 20)) % 3 == 0:
                        self._cell(c, cell, dim(r.color, k * 0.6))
                continue
            n = len(r.trail)
            for j, cell in enumerate(r.trail):
                fade = 0.45 + 0.55 * (j / max(1, n - 1))
                self._cell(c, cell, dim(r.color, fade))
            head = lerp(r.color, WHITE, 0.6)
            if self._phase is Phase.OVER and self.winner == i and int(frame.monotonic * 6) % 2 == 0:
                head = WHITE
            self._cell(c, r.pos, head)
