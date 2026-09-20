"""Snake plays itself: breadth-first search to the food, but only if the snake can still reach
its own tail afterwards; otherwise it stalls by chasing its tail until a safe route appears.
Sooner or later it traps itself, flashes, and starts over."""

from __future__ import annotations

import random
from collections import deque
from enum import Enum

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.snake.settings import SnakeSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

Cell = tuple[int, int]
DIRS: tuple[Cell, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


class Phase(Enum):
    PLAY = "play"
    DEAD = "dead"


def bfs(start: Cell, goal: Cell, blocked: set[Cell], cols: int, rows: int) -> list[Cell] | None:
    """Shortest path from start to goal (excluding start), or None."""
    if start == goal:
        return []
    parent: dict[Cell, Cell] = {}
    seen = {start}
    q: deque[Cell] = deque([start])
    while q:
        cur = q.popleft()
        for dx, dy in DIRS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if not (0 <= nxt[0] < cols and 0 <= nxt[1] < rows) or nxt in seen or (nxt in blocked and nxt != goal):
                continue
            seen.add(nxt)
            parent[nxt] = cur
            if nxt == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                path.reverse()
                return path[1:]
            q.append(nxt)
    return None


class SnakeModule(Module[SnakeSettings]):
    info = ModuleInfo(
        id="snake",
        name="Snake",
        description="Idle animation: Snake plays itself until it traps itself, then starts over.",
        tier=Tier.NEED,
        icon="snake",
        default_duration_s=90,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = SnakeSettings

    def __init__(self, ctx: ModuleContext, settings: SnakeSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._reset(ctx.size)

    def _cell_px(self, size: Size) -> int:
        if self.settings.cell_px:
            return self.settings.cell_px
        return 4 if min(size.w, size.h) >= 96 else 2

    def _reset(self, size: Size) -> None:
        self.px = self._cell_px(size)
        self.cols, self.rows = max(4, size.w // self.px), max(4, size.h // self.px)
        self.ox, self.oy = (size.w - self.cols * self.px) // 2, (size.h - self.rows * self.px) // 2
        cx, cy = self.cols // 2, self.rows // 2
        n = min(self.settings.start_length, self.cols // 2)
        self.snake: deque[Cell] = deque((cx - i, cy) for i in range(n))  # head first
        self.direction: Cell = (1, 0)
        self.food = self._place_food()
        self.eaten = 0
        self._acc = 0.0
        self._phase = Phase.PLAY
        self._timer = 0.0

    def _place_food(self) -> Cell:
        body = set(self.snake)
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in body]
        return self.rng.choice(free) if free else self.snake[-1]

    # ---- AI -------------------------------------------------------------------------------

    def _reachable_tail(self, snake: deque[Cell]) -> bool:
        body = set(snake)
        body.discard(snake[-1])
        return bfs(snake[0], snake[-1], body, self.cols, self.rows) is not None

    def _next_move(self) -> Cell | None:
        head = self.snake[0]
        body = set(self.snake)
        body.discard(self.snake[-1])  # the tail moves away this step
        path = bfs(head, self.food, body, self.cols, self.rows)
        if path:
            step = path[0]
            trial = deque(self.snake)
            trial.appendleft(step)
            if step != self.food:
                trial.pop()
            if self._reachable_tail(trial) or len(trial) >= self.cols * self.rows - 1:
                return step
        # No safe route to food: follow the tail (longest safe wander), preferring to stay away from food.
        candidates: list[tuple[int, Cell]] = []
        for dx, dy in DIRS:
            nxt = (head[0] + dx, head[1] + dy)
            if not (0 <= nxt[0] < self.cols and 0 <= nxt[1] < self.rows) or nxt in body:
                continue
            trial = deque(self.snake)
            trial.appendleft(nxt)
            trial.pop()
            if self._reachable_tail(trial):
                dist = abs(nxt[0] - self.food[0]) + abs(nxt[1] - self.food[1])
                candidates.append((dist, nxt))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
        # Last resort: any free neighbor
        for dx, dy in DIRS:
            nxt = (head[0] + dx, head[1] + dy)
            if 0 <= nxt[0] < self.cols and 0 <= nxt[1] < self.rows and nxt not in body:
                return nxt
        return None

    def step(self) -> bool:
        """Advance one move; returns False when the game just ended."""
        nxt = self._next_move()
        if nxt is None:
            self._phase, self._timer = Phase.DEAD, 0.0
            return False
        self.direction = (nxt[0] - self.snake[0][0], nxt[1] - self.snake[0][1])
        self.snake.appendleft(nxt)
        if nxt == self.food:
            self.eaten += 1
            if len(self.snake) >= self.cols * self.rows:
                self._phase, self._timer = Phase.DEAD, 0.0  # perfect game
                return False
            self.food = self._place_food()
        else:
            self.snake.pop()
        return True

    # ---- animation ---------------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        if self._phase is Phase.PLAY:
            self._acc += dt * self.settings.speed
            steps = int(self._acc)
            self._acc -= steps
            for _ in range(min(steps, 6)):
                if not self.step():
                    break
        else:
            self._timer += dt
            if self._timer >= self.settings.pause_s:
                self._reset(self.ctx.size)

    async def on_settings_changed(self, settings: SnakeSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    def on_enter(self) -> None:
        self._reset(self.ctx.size)

    def _cell_rect(self, c: Canvas, cell: Cell, color: Color) -> None:
        gap = 1 if self.px >= 3 else 0
        c.rect(self.ox + cell[0] * self.px, self.oy + cell[1] * self.px, self.px - gap, self.px - gap, fill=color)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if self._cell_px(c.size) != self.px or self.cols * self.px > c.width or self.rows * self.px > c.height:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        head_c, body_c, food_c = (
            parse_color(self.settings.head_color),
            parse_color(self.settings.body_color),
            parse_color(self.settings.food_color),
        )
        n = len(self.snake)
        dead = self._phase is Phase.DEAD
        flash = dead and int(self._timer * 6) % 2 == 0
        for i, cell in enumerate(self.snake):
            if i == 0:
                col = (255, 60, 60) if flash else head_c
            else:
                col = lerp(body_c, dim(body_c, 0.35), i / max(1, n - 1))
                if flash:
                    col = dim(col, 0.4)
            self._cell_rect(c, cell, col)
        if not dead:
            blink = 0.7 + 0.3 * (int(frame.monotonic * 4) % 2)
            self._cell_rect(c, self.food, dim(food_c, blink))
