from __future__ import annotations

import pytest

from homely.core.module import FrameInfo
from homely.modules.lightcycles.module import LightCyclesModule, Phase
from homely.modules.lightcycles.settings import LightCyclesSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden


def frame(dt: float, elapsed: float) -> FrameInfo:
    return FrameInfo(now=FROZEN, monotonic=100.0 + elapsed, dt=dt, index=0, slot_elapsed=elapsed, slot_duration=90)


def run_frames(mod, size: Size, n: int, dt: float = 1 / 30):
    canvas = Canvas(size)
    for i in range(n):
        canvas.clear()
        mod.render(canvas, frame(dt, i * dt))
    return canvas.snapshot()


def test_riders_leave_walls_and_never_overlap():
    mod = LightCyclesModule(make_ctx(Size(64, 64)), LightCyclesSettings(cycles=4, speed=60), seed=1)
    run_frames(mod, Size(64, 64), 30)  # 1 s: 60 moves
    cells = [c for r in mod.riders for c in r.trail]
    assert len(cells) == len(set(cells)) and len(cells) > 60
    assert all(0 <= x < mod.cols and 0 <= y < mod.rows for x, y in cells)
    for r in mod.riders:
        if r.alive:
            assert r.trail[-1] == r.pos


def test_round_ends_with_at_most_one_survivor_and_restarts():
    mod = LightCyclesModule(make_ctx(Size(32, 32)), LightCyclesSettings(cycles=2, speed=80, pause_s=0.3), seed=2)
    canvas = Canvas(Size(32, 32))
    ended = False
    for i in range(600):
        canvas.clear()
        mod.render(canvas, frame(1 / 30, i / 30))
        if mod._phase is Phase.OVER:
            ended = True
            assert sum(r.alive for r in mod.riders) <= 1
            break
    assert ended
    run_frames(mod, Size(32, 32), 15)  # pause elapses: a fresh round is under way
    assert mod._phase is Phase.RACE and all(r.alive for r in mod.riders)
    assert all(len(r.trail) < 40 for r in mod.riders)


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_lightcycles(size, request):
    mod = LightCyclesModule(make_ctx(size), LightCyclesSettings(), seed=42)
    assert_golden(run_frames(mod, size, 60), f"lightcycles/{size}/frame_60", request)


@pytest.mark.parametrize("palette", ["neon", "duel"])
def test_golden_lightcycles_palettes(palette, request):
    mod = LightCyclesModule(make_ctx(Size(64, 64)), LightCyclesSettings(cycles=4, palette=palette), seed=42)
    assert_golden(run_frames(mod, Size(64, 64), 90), f"lightcycles/64x64/{palette}_4", request)
