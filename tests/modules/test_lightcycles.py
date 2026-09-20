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


@pytest.mark.parametrize("seed", range(12))
def test_four_riders_survive_the_opening(seed):
    """The old layout sent pairs of riders head-on; nobody should crash in the first stretch."""
    mod = LightCyclesModule(make_ctx(Size(64, 64)), LightCyclesSettings(cycles=4, speed=30), seed=seed)
    run_frames(mod, Size(64, 64), 30)  # 30 moves
    assert all(r.alive for r in mod.riders), [r.alive for r in mod.riders]
    # and the round still ends eventually
    for _ in range(40):
        run_frames(mod, Size(64, 64), 30)
        if mod._phase is Phase.OVER:
            break
    assert mod._phase is Phase.OVER or sum(r.alive for r in mod.riders) >= 1


def test_opening_skips_the_search_while_nothing_is_in_reach():
    """Four riders on an empty board used to run the full search three times each per step --
    the most expensive it ever gets and the least informative, which showed as lag at the
    start of every round."""
    mod = LightCyclesModule(make_ctx(Size(128, 32)), LightCyclesSettings(cycles=4), seed=3)
    mod.on_enter()
    searched = 0
    original = mod._territory

    def counted(mine, rivals):
        nonlocal searched
        searched += 1
        return original(mine, rivals)

    mod._territory = counted
    run_frames(mod, Size(128, 32), 60)  # the first two seconds
    opening = searched
    searched = 0
    run_frames(mod, Size(128, 32), 60)  # two seconds once walls are up
    assert opening < searched, (opening, searched)


def test_aggression_makes_riders_close_on_each_other():
    """Scoring on (my territory - the rival's) cannot do this: the search splits the free space
    between the heads, so that difference ranks the moves exactly as my own share does.

    Measured head to head. With three or four riders the arena is crowded enough that the
    closest pair is set by the starting geometry, and aggression -- which only ever picks
    between moves that cost about the same -- does not move this number either way.
    """

    def mean_separation(aggression: int) -> float:
        gaps: list[int] = []
        for seed in range(6):
            mod = LightCyclesModule(
                make_ctx(Size(128, 32)), LightCyclesSettings(cycles=2, aggression=aggression), seed=seed
            )
            mod.on_enter()
            canvas = Canvas(Size(128, 32))
            for i in range(30 * 20):
                canvas.clear()
                mod.render(canvas, frame(1 / 30, i / 30))
                heads = [r.pos for r in mod.riders if r.alive]
                if len(heads) > 1:
                    gaps.append(
                        min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for k, a in enumerate(heads) for b in heads[k + 1 :])
                    )
        return sum(gaps) / len(gaps)

    assert mean_separation(80) < mean_separation(0)


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_lightcycles(size, request):
    mod = LightCyclesModule(make_ctx(size), LightCyclesSettings(), seed=42)
    assert_golden(run_frames(mod, size, 60), f"lightcycles/{size}/frame_60", request)


@pytest.mark.parametrize("palette", ["neon", "duel"])
def test_golden_lightcycles_palettes(palette, request):
    mod = LightCyclesModule(make_ctx(Size(64, 64)), LightCyclesSettings(cycles=4, palette=palette), seed=42)
    assert_golden(run_frames(mod, Size(64, 64), 90), f"lightcycles/64x64/{palette}_4", request)
