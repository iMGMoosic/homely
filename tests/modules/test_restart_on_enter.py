"""Flipping to a module restarts it, rather than resuming where its last turn left off."""

from __future__ import annotations

import pytest

from homely.core.module import FrameInfo, Module
from homely.modules import BUILTIN_MODULES
from homely.modules.lightcycles.module import LightCyclesModule
from homely.modules.lightcycles.settings import LightCyclesSettings
from homely.modules.maze.module import MazeModule
from homely.modules.maze.settings import MazeSettings
from homely.modules.tvstatic.module import Mode, TvStaticModule
from homely.modules.tvstatic.settings import TvStaticSettings
from homely.render.canvas import Canvas
from homely.render.size import Size
from tests.conftest import FROZEN, make_ctx

# Modules whose whole output is derived from the clock or from polled data: there is nothing
# for a turn to restart, so they keep the base class's do-nothing on_enter.
STATELESS = {"clock", "weather"}


def run_frames(mod, size: Size, n: int, dt: float = 1 / 30):
    canvas = Canvas(size)
    for i in range(n):
        canvas.clear()
        frame = FrameInfo(now=FROZEN, monotonic=100.0 + i * dt, dt=dt, index=i, slot_elapsed=i * dt, slot_duration=120)
        mod.render(canvas, frame)
    return canvas.snapshot()


@pytest.mark.parametrize("cls", BUILTIN_MODULES, ids=lambda c: c.info.id)
def test_module_restarts_when_flipped_to(cls):
    assert (cls.on_enter is not Module.on_enter) == (cls.info.id not in STATELESS), cls.info.id


def test_maze_starts_a_new_maze_each_turn():
    size = Size(128, 32)
    mod = MazeModule(make_ctx(size), MazeSettings(), seed=1)
    run_frames(mod, size, 120)
    assert mod._drawn > 0
    grid = mod.grid
    mod.on_enter()
    assert mod.grid is not grid
    assert mod._drawn == 0 and mod._img is not None and mod._img.getbbox() is None


def test_lightcycles_starts_a_new_round_each_turn():
    size = Size(128, 32)
    mod = LightCyclesModule(make_ctx(size), LightCyclesSettings(cycles=2, speed=60), seed=1)
    run_frames(mod, size, 120)
    assert max(len(r.trail) for r in mod.riders) > 10
    mod.on_enter()
    assert all(r.alive and len(r.trail) == 1 for r in mod.riders)


def test_tv_static_tunes_in_fresh_each_turn():
    size = Size(64, 32)
    mod = TvStaticModule(make_ctx(size), TvStaticSettings(flip_every_s=2.0), seed=1)
    run_frames(mod, size, 120)
    mod.timer = 99.0
    mod.on_enter()
    assert mod.mode is Mode.STATIC and mod.timer == 0.0 and mod.channel == 0
