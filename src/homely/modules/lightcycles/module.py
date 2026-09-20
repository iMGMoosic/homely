"""Light cycles: riders race across the arena leaving solid light walls behind them.

Steering is the classic Tron-bot heuristic. For every legal move a rider runs one multi-source
breadth-first search from its own would-be head and every rival head at once, and counts the
cells it would reach strictly sooner than anyone else: its territory. That single number covers
both halves of the game -- do not get boxed in, and do not hand the board away -- where a plain
flood fill only measured the first. On top of it a rider refuses moves with no exit (suicide on
the following step), hugs walls on ties so it packs its own space tightly instead of leaving
unusable slivers, and keeps going straight only while that costs it almost no territory. The
`aggression` setting then spends some of that territory: among the moves that cost it little,
a rider takes the one that closes on a rival rather than the one that simply banks the most
space. When nothing is within reach to tell the moves apart, the search is skipped entirely --
running it on an empty board is both the most expensive it ever gets and the least informative,
and it was what made three and four riders stutter at the start of a round.

Crashing derezzes a trail; the last rider standing wins the round."""

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
ARENA_CELLS = 1200  # automatic cell size keeps the arena to about this many cells
FLOOD_CAP = ARENA_CELLS + 100  # so a search covers the whole arena instead of truncating
CONTESTED = -1  # territory owner for cells two riders reach on the same step
STRAIGHT_KEEP = 0.9  # go straight while it keeps this much of the best move's territory
GIVE_UP_FOR_BLOOD = 0.25  # share of its own territory a fully aggressive rider will trade to crowd a rival


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
        # Fat cells on big panels. A 128x32 board is 4096 single pixels: hairline trails that
        # barely read on a LED panel, and far more cells than a rider can search before it has
        # to commit to a move, which is what made riders wall themselves in.
        px = 1
        while px < 4 and (size.w // px) * (size.h // px) > ARENA_CELLS:
            px += 1
        return px

    def _reset(self, size: Size) -> None:
        self.px = self._cell_px(size)
        self.cols, self.rows = max(8, size.w // self.px), max(8, size.h // self.px)
        self.ox, self.oy = (size.w - self.cols * self.px) // 2, (size.h - self.rows * self.px) // 2
        self.walls: dict[Cell, int] = {}  # cell -> rider index
        colors = PALETTES[self.settings.palette]
        n = self.settings.cycles
        # Pinwheel starts: each rider begins near an edge heading along it, so nobody faces
        # another rider at the start (the old layout sent pairs straight into each other).
        # The exact spots are jittered because the steering itself is near-deterministic: with
        # fixed starts every round of a given size would play out identically.
        cx = self.rng.randint(self.cols // 3, max(self.cols // 3, 2 * self.cols // 3))
        cy = self.rng.randint(self.rows // 3, max(self.rows // 3, 2 * self.rows // 3))
        mx = self.rng.randint(max(1, self.cols // 8), max(1, self.cols // 3))
        my = self.rng.randint(max(1, self.rows // 8), max(1, self.rows // 3))
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

    def _territory(self, mine: Cell, rivals: list[Cell]) -> int:
        """Cells reachable from `mine` strictly sooner than from any rival head (capped).

        One breadth-first wave is grown from every head at once; each cell is claimed by
        whichever head arrives first, and cells reached on the same step by two heads go to
        nobody. With no rivals left this is just a flood fill, which is what we want: then the
        only thing that matters is not sealing yourself in.
        """
        if not self._free(mine):
            return 0
        # This is the hot loop of the whole module, so the bounds/wall test is inlined rather
        # than going through _free() for every neighbour of every visited cell.
        cols, rows, walls = self.cols, self.rows, self.walls
        owner: dict[Cell, int] = {mine: 0}
        dist: dict[Cell, int] = {mine: 0}
        q: deque[tuple[int, int, int, int]] = deque([(mine[0], mine[1], 0, 0)])
        for i, head in enumerate(rivals, start=1):
            owner[head] = i
            dist[head] = 0
            q.append((head[0], head[1], i, 0))
        count = 1
        visited = len(owner)
        while q and visited < FLOOD_CAP:
            x, y, who, d = q.popleft()
            if owner[(x, y)] != who:
                continue  # this cell was contested after it went into the queue
            nd = d + 1
            for dx, dy in DIRS:
                nx, ny = x + dx, y + dy
                if nx < 0 or nx >= cols or ny < 0 or ny >= rows:
                    continue
                nxt = (nx, ny)
                if nxt in walls:
                    continue
                seen_at = dist.get(nxt)
                if seen_at is None:
                    dist[nxt], owner[nxt] = nd, who
                    visited += 1
                    if who == 0:
                        count += 1
                    q.append((nx, ny, who, nd))
                elif seen_at == nd and owner[nxt] not in (who, CONTESTED):
                    if owner[nxt] == 0:
                        count -= 1
                    owner[nxt] = CONTESTED
        return count

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

    def _exits(self, cell: Cell) -> int:
        return sum(1 for dx, dy in DIRS if self._free((cell[0] + dx, cell[1] + dy)))

    def _coasting(self, r: Rider, rivals: list[Cell]) -> bool:
        """True when nothing is close enough for the search to tell the options apart.

        Running it anyway is what made three and four riders stutter for the first seconds of a
        round: on an empty board every option floods the whole arena, which is the most
        expensive the search ever gets and the least informative.
        """
        reach = self.settings.lookahead
        if self._clear_ahead(r.pos, r.direction) < reach:
            return False
        x, y = r.pos
        if min((abs(x - rx) + abs(y - ry) for rx, ry in rivals), default=99) <= reach + 2:
            return False
        # Both flanks open for a few cells too, so it is not skimming along a wall it should
        # be turning away from.
        return all(self._clear_ahead(r.pos, (r.direction + turn) % 4) >= 2 for turn in (1, -1))

    def _choose(self, r: Rider) -> int | None:
        options = [r.direction, (r.direction + 1) % 4, (r.direction - 1) % 4]
        rivals = [o.pos for o in self.riders if o is not r and o.alive]
        if self._coasting(r, rivals):
            return r.direction
        danger = self._danger(r)
        legal = [d for d in options if self._free((r.pos[0] + DIRS[d][0], r.pos[1] + DIRS[d][1]))]
        aggression = self.settings.aggression / 100
        scored: list[tuple[float, int, int]] = []  # (score, territory, direction)
        for d in legal:
            nxt = (r.pos[0] + DIRS[d][0], r.pos[1] + DIRS[d][1])
            exits = self._exits(nxt)
            if exits == 0:
                continue  # a pocket: moving in means crashing on the very next step
            room = self._territory(nxt, rivals)
            ahead = self._clear_ahead(r.pos, d, danger)
            # Territory dominates. Once a rider is boxed into a region it can count to the end
            # (room below the cap), fewer exits breaks ties, which packs its own space tightly
            # instead of stranding one-cell slivers. In the open, where the search saturates and
            # every option scores the same, that term would just spiral it into a corner, so out
            # there `ahead` decides and riders run long clean lines.
            score = room * 4 + ahead * 2 + self.rng.random() * 3
            if room < FLOOD_CAP:
                score -= exits
            if nxt in danger:
                score -= 8 * FLOOD_CAP  # a rival may take this cell on the same step
            scored.append((score, room, d))
        if not scored:
            # Every option is fatal; still move, so the crash looks like a crash.
            return self.rng.choice(legal) if legal else None
        scored.sort(reverse=True)
        safe = [(score, room, d) for score, room, d in scored if score > -FLOOD_CAP]
        best_room = max((room for _, room, _ in safe), default=0)
        if aggression and rivals and safe:
            # Scoring on (my territory - the rival's) cannot make a rider play the other riders:
            # the search splits the free space between the heads, so that difference is a
            # monotonic function of my own share and ranks the moves in exactly the same order.
            # Aggression instead spends territory. Every move that stays within `give_up` of the
            # best is a contender, and among those the rider takes the one that closes on a
            # rival -- crowding it, and cutting its room off sooner.
            give_up = best_room * (1 - GIVE_UP_FOR_BLOOD * aggression)
            contenders = [(room, d) for _, room, d in safe if room >= give_up]
            if len(contenders) > 1:
                # Ties go to holding the line, then to the roomier move.
                def hunt(candidate: tuple[int, int]) -> tuple[int, bool, int]:
                    room, d = candidate
                    return self._closeness(r, d, rivals), d != r.direction, -room

                return min(contenders, key=hunt)[1]
        for _, room, d in safe:
            # Holding a line looks far better than jittering, so keep straight unless it
            # actually costs territory.
            if d == r.direction and room >= best_room * STRAIGHT_KEEP:
                return d
        return scored[0][2]

    def _closeness(self, r: Rider, d: int, rivals: list[Cell]) -> int:
        x, y = r.pos[0] + DIRS[d][0], r.pos[1] + DIRS[d][1]
        return min(abs(x - rx) + abs(y - ry) for rx, ry in rivals)

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

    def on_enter(self) -> None:
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
