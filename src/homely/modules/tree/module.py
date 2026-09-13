"""Growing tree (space colonization): attraction points fill a canopy shape; branches grow toward
the nearest points and consume them, so the tree fills the canopy naturally. Then leaves bud at
the tips, turn autumn colors, fall to the ground, and a new sapling starts."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum

from PIL import ImageDraw

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.tree.settings import TreeSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size


class Phase(Enum):
    GROW = "grow"
    LEAF = "leaf"
    HOLD = "hold"
    AUTUMN = "autumn"
    FALL = "fall"
    FADE = "fade"


@dataclass
class Node:
    x: float
    y: float
    parent: int | None
    children: list[int] = field(default_factory=list)
    weight: int = 1  # number of tips downstream (thickness)


@dataclass
class Leaf:
    x: float
    y: float
    vy: float = 0.0
    vx: float = 0.0
    color: Color = (0, 0, 0)
    born: float = 0.0
    landed: bool = False


class TreeModule(Module[TreeSettings]):
    info = ModuleInfo(
        id="tree",
        name="Growing tree",
        description="Idle animation: a tree grows branch by branch, leafs out, turns, and sheds.",
        tier=Tier.NEED,
        icon="tree",
        default_duration_s=90,
        default_fps=30,
        min_size=Size(24, 24),
    )
    Settings = TreeSettings

    def __init__(self, ctx: ModuleContext, settings: TreeSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._reset(ctx.size)

    # ---- setup ---------------------------------------------------------------------------------

    def _reset(self, size: Size) -> None:
        w, h = size.w, size.h
        self.size = size
        scale = min(w, h) / 64
        self.seg = max(1.5, 2.2 * scale)  # branch segment length
        self.attract_r = self.seg * 6
        self.kill_r = self.seg * 1.6
        ground = h - 2
        trunk_x = w / 2 + self.rng.uniform(-w * 0.08, w * 0.08)
        self.nodes: list[Node] = [Node(trunk_x, ground, None)]
        # a few trunk segments straight up before the canopy takes over
        for i in range(1, max(3, int(h * 0.12 / self.seg))):
            self.nodes.append(Node(trunk_x + self.rng.uniform(-0.3, 0.3), ground - i * self.seg, i - 1))
            self.nodes[i - 1].children.append(i)
        cx, cy = w / 2, h * 0.42
        rx, ry = w * self.rng.uniform(0.32, 0.46), h * self.rng.uniform(0.26, 0.36)
        self.attractors: list[tuple[float, float]] = []
        target = int(90 * scale * scale) + 40
        while len(self.attractors) < target:
            ax, ay = self.rng.uniform(cx - rx, cx + rx), self.rng.uniform(cy - ry, cy + ry)
            if ((ax - cx) / rx) ** 2 + ((ay - cy) / ry) ** 2 <= 1.0:
                self.attractors.append((ax, ay))
        # Keep the trunk climbing until the canopy is within reach, so every seed grows a tree.
        while len(self.nodes) < 60:
            top = self.nodes[-1]
            if any(math.hypot(ax - top.x, ay - top.y) <= self.attract_r for ax, ay in self.attractors):
                break
            self.nodes.append(Node(top.x + self.rng.uniform(-0.3, 0.3), top.y - self.seg, len(self.nodes) - 1))
            self.nodes[-2].children.append(len(self.nodes) - 1)
        self.leaves: list[Leaf] = []
        self._phase = Phase.GROW
        self._timer = 0.0
        self._acc = 0.0
        self._stuck = 0
        self._season = 0.0
        self._fade = 1.0
        self.ground = ground

    # ---- growth (space colonization) --------------------------------------------------------------

    def grow_step(self) -> bool:
        """One growth iteration; returns False when the tree has stopped growing."""
        influences: dict[int, list[tuple[float, float]]] = {}
        remaining: list[tuple[float, float]] = []
        for ax, ay in self.attractors:
            best, best_d = -1, self.attract_r
            for i, n in enumerate(self.nodes):
                d = math.hypot(ax - n.x, ay - n.y)
                if d < best_d:
                    best, best_d = i, d
            if best >= 0 and best_d <= self.kill_r:
                continue  # reached: consumed
            remaining.append((ax, ay))
            if best >= 0:
                influences.setdefault(best, []).append((ax, ay))
        self.attractors = remaining
        if not influences:
            self._stuck += 1
            return self._stuck < 3 and bool(self.attractors)
        for i, pts in influences.items():
            n = self.nodes[i]
            dx = sum(px - n.x for px, _ in pts)
            dy = sum(py - n.y for _, py in pts)
            length = math.hypot(dx, dy) or 1.0
            dx, dy = dx / length, dy / length
            dx += self.rng.uniform(-0.15, 0.15)
            dy += self.rng.uniform(-0.15, 0.15) - 0.05  # slight upward bias
            length = math.hypot(dx, dy) or 1.0
            new = Node(n.x + dx / length * self.seg, n.y + dy / length * self.seg, i)
            self.nodes.append(new)
            n.children.append(len(self.nodes) - 1)
        return True

    def _compute_weights(self) -> None:
        for n in self.nodes:
            n.weight = 0
        for idx in range(len(self.nodes) - 1, -1, -1):
            n = self.nodes[idx]
            if not n.children:
                n.weight = 1
            if n.parent is not None:
                self.nodes[n.parent].weight += n.weight

    def _bud_leaves(self) -> None:
        leaf = parse_color(self.settings.leaf_color)
        tips = [n for n in self.nodes if not n.children and n.parent is not None]
        for n in tips:
            for _ in range(2 if self.size.w >= 64 else 1):
                jitter = self.seg * 0.9
                self.leaves.append(
                    Leaf(
                        x=n.x + self.rng.uniform(-jitter, jitter),
                        y=n.y + self.rng.uniform(-jitter, jitter),
                        color=lerp(leaf, dim(leaf, 0.6), self.rng.random()),
                        born=self.rng.uniform(0, 1.5),
                    )
                )

    # ---- animation ------------------------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        if self._phase is Phase.GROW:
            self._acc += dt * self.settings.speed
            steps = int(self._acc)
            self._acc -= steps
            for _ in range(min(steps, 4)):
                if not self.grow_step() or len(self.nodes) > 900:
                    self._compute_weights()
                    self._bud_leaves()
                    self._phase, self._timer = Phase.LEAF, 0.0
                    break
        elif self._phase is Phase.LEAF:
            self._timer += dt
            if self._timer >= 1.8:
                self._phase, self._timer = Phase.HOLD, 0.0
        elif self._phase is Phase.HOLD:
            self._timer += dt
            if self._timer >= self.settings.hold_s:
                self._phase, self._timer = (Phase.AUTUMN if self.settings.seasons else Phase.FADE), 0.0
        elif self._phase is Phase.AUTUMN:
            self._timer += dt
            self._season = min(1.0, self._timer / 3.0)
            if self._timer >= 3.5:
                self._phase, self._timer = Phase.FALL, 0.0
                for lf in self.leaves:
                    lf.vy = self.rng.uniform(4, 12)
                    lf.vx = self.rng.uniform(-6, 6)
                    lf.born = self.rng.uniform(0, 2.5)  # staggered release
        elif self._phase is Phase.FALL:
            self._timer += dt
            for lf in self.leaves:
                if self._timer < lf.born or lf.landed:
                    continue
                lf.vy = min(30, lf.vy + 20 * dt)
                lf.x += lf.vx * dt + math.sin(self._timer * 3 + lf.born) * 4 * dt
                lf.y += lf.vy * dt
                if lf.y >= self.ground:
                    lf.y, lf.landed = self.ground, True
            if self._timer >= 5.0:
                self._phase, self._timer = Phase.FADE, 0.0
        else:
            self._timer += dt
            self._fade = max(0.0, 1.0 - self._timer / 1.2)
            if self._timer >= 1.3:
                self._reset(self.ctx.size)

    async def on_settings_changed(self, settings: TreeSettings) -> None:
        self.settings = settings
        self._reset(self.ctx.size)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if c.size != self.size:
            self._reset(c.size)
        self.advance(min(frame.dt, 0.25))
        trunk = parse_color(self.settings.trunk_color)
        if self._phase is Phase.GROW:
            self._compute_weights()
        draw = ImageDraw.Draw(c.image)
        ox, oy = c._abs(0, 0)
        max_w = max(1, max((n.weight for n in self.nodes), default=1))
        for n in self.nodes:
            if n.parent is None:
                continue
            p = self.nodes[n.parent]
            width = 1 + int(2.5 * (n.weight / max_w) ** 0.5) if c.width >= 48 else 1
            col = dim(trunk, self._fade * (0.75 + 0.25 * (n.weight / max_w)))
            draw.line((ox + p.x, oy + p.y, ox + n.x, oy + n.y), fill=col, width=width)
        autumn = parse_color(self.settings.autumn_color)
        show_t = self._timer if self._phase is Phase.LEAF else 99.0
        for lf in self.leaves:
            if self._phase is Phase.LEAF and lf.born > show_t:
                continue
            col = (
                lerp(lf.color, lerp(autumn, dim(autumn, 0.5), (lf.x * 7 + lf.y * 3) % 1.0), self._season)
                if self._season
                else lf.color
            )
            if lf.landed:
                col = dim(col, 0.55)
            c.pixel(int(lf.x), int(lf.y), dim(col, self._fade))
        # ground line
        c.hline(0, c.height - 1, c.width, dim((60, 90, 40), self._fade))
