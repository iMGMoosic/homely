from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homely.core.module import FrameInfo
from homely.modules.skyline.module import SkylineModule
from homely.modules.skyline.settings import SkylineSettings
from homely.modules.snake.module import Phase as SnakePhase
from homely.modules.snake.module import SnakeModule, bfs
from homely.modules.snake.settings import SnakeSettings
from homely.modules.tree.module import Phase as TreePhase
from homely.modules.tree.module import TreeModule
from homely.modules.tree.settings import TreeSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden

CHI = ZoneInfo("America/Chicago")


def frame(dt: float, elapsed: float, now: datetime = FROZEN) -> FrameInfo:
    return FrameInfo(now=now, monotonic=100.0 + elapsed, dt=dt, index=0, slot_elapsed=elapsed, slot_duration=120)


def run_frames(mod, size: Size, n: int, dt: float = 1 / 30, now: datetime = FROZEN):
    canvas = Canvas(size)
    for i in range(n):
        canvas.clear()
        mod.render(canvas, frame(dt, i * dt, now))
    return canvas.snapshot()


def lit(img):
    return sum(1 for p in img.getdata() if p != (0, 0, 0))


# ---- snake -----------------------------------------------------------------------------------


def test_bfs_routes_around_blocks():
    path = bfs((0, 0), (2, 0), {(1, 0)}, 3, 3)
    assert path is not None and path[-1] == (2, 0) and (1, 0) not in path
    assert bfs((0, 0), (2, 0), {(1, 0), (1, 1), (1, 2)}, 3, 3) is None


def test_snake_eats_and_grows_without_dying_early():
    mod = SnakeModule(make_ctx(Size(64, 64)), SnakeSettings(speed=40), seed=1)
    start_len = len(mod.snake)
    run_frames(mod, Size(64, 64), 150)  # 5 s at 40 moves/s = 200 moves
    assert mod.eaten >= 3 and len(mod.snake) == start_len + mod.eaten
    body = list(mod.snake)
    assert len(set(body)) == len(body)  # never overlaps itself
    for x, y in body:
        assert 0 <= x < mod.cols and 0 <= y < mod.rows


def test_snake_restarts_after_death():
    mod = SnakeModule(make_ctx(Size(16, 16)), SnakeSettings(cell_px=4, speed=40, pause_s=0.2), seed=2)
    mod._phase, mod._timer = SnakePhase.DEAD, 0.0
    run_frames(mod, Size(16, 16), 15)
    assert mod._phase is SnakePhase.PLAY and len(mod.snake) <= 8


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_snake(size, request):
    mod = SnakeModule(make_ctx(size), SnakeSettings(), seed=42)
    assert_golden(run_frames(mod, size, 60), f"snake/{size}/frame_60", request)


# ---- tree ---------------------------------------------------------------------------------------


def test_tree_grows_leafs_and_sheds():
    mod = TreeModule(make_ctx(Size(64, 64)), TreeSettings(speed=60, hold_s=0.2), seed=3)
    run_frames(mod, Size(64, 64), 90)  # 3 s: growth finishes at 60 steps/s
    assert len(mod.nodes) > 30 and mod._phase in (
        TreePhase.LEAF,
        TreePhase.HOLD,
        TreePhase.AUTUMN,
        TreePhase.FALL,
        TreePhase.FADE,
    )
    assert mod.leaves
    run_frames(mod, Size(64, 64), 400)  # seasons pass and a new sapling starts
    assert mod._phase in (TreePhase.GROW, TreePhase.LEAF) or len(mod.nodes) < 30 or all(lf.landed for lf in mod.leaves)


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_tree(size, request):
    mod = TreeModule(make_ctx(size), TreeSettings(speed=30), seed=42)
    img = run_frames(mod, size, 120)  # 4 s
    assert lit(img) > 20
    assert_golden(img, f"tree/{size}/frame_120", request)


def test_golden_tree_autumn(request):
    mod = TreeModule(make_ctx(Size(64, 64)), TreeSettings(speed=60, hold_s=0.1), seed=42)
    run_frames(mod, Size(64, 64), 60)
    assert mod._phase is not TreePhase.GROW
    mod._phase, mod._timer = TreePhase.AUTUMN, 2.5
    assert_golden(run_frames(mod, Size(64, 64), 1), "tree/64x64/autumn", request)


# ---- skyline --------------------------------------------------------------------------------------


def make_skyline(size: Size, now: datetime, **kw) -> SkylineModule:
    ctx = make_ctx(size, now=now)
    ctx.location.config.latitude, ctx.location.config.longitude = 44.98, -93.27
    return SkylineModule(ctx, SkylineSettings(mode="realtime", **kw), seed=42)


@pytest.mark.parametrize(
    "label,hour",
    [("night", 2), ("dawn", 6), ("day", 13), ("dusk", 19), ("evening", 21)],
)
def test_golden_skyline_times(label, hour, request):
    now = datetime(2026, 9, 13, hour, 20, tzinfo=CHI)
    mod = make_skyline(Size(64, 64), now)
    assert_golden(run_frames(mod, Size(64, 64), 30, now=now), f"skyline/64x64/{label}", request)


def test_skyline_timelapse_advances_through_the_day():
    mod = SkylineModule(make_ctx(Size(64, 32)), SkylineSettings(mode="timelapse", day_length_s=60), seed=1)
    c = Canvas(Size(64, 32))
    mod.render(c, frame(0.0, 0.0))
    early = mod._now(frame(0.0, 0.0))
    late = mod._now(frame(0.0, 30.0))
    assert (late - early).total_seconds() == pytest.approx(12 * 3600)
    assert mod.buildings and any(b.windows for b in mod.buildings)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(64, 64)], ids=str)
def test_golden_skyline_sizes(size, request):
    now = datetime(2026, 9, 13, 20, 40, tzinfo=CHI)
    mod = make_skyline(size, now)
    img = run_frames(mod, size, 20, now=now)
    assert img.size == size.as_tuple()
    assert_golden(img, f"skyline/{size}/evening", request)
