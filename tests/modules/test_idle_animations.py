from __future__ import annotations

import pytest

from homely.core.module import FrameInfo
from homely.modules.maze.module import MazeModule, Phase
from homely.modules.maze.settings import MazeSettings
from homely.modules.qix.module import QixModule
from homely.modules.qix.settings import QixSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden


def frame(dt: float, elapsed: float) -> FrameInfo:
    return FrameInfo(now=FROZEN, monotonic=100.0 + elapsed, dt=dt, index=0, slot_elapsed=elapsed, slot_duration=60)


def run_frames(mod, size: Size, n: int, dt: float = 1 / 30):
    canvas = Canvas(size)
    for i in range(n):
        canvas.clear()
        mod.render(canvas, frame(dt, i * dt))
    return canvas.snapshot()


def lit(img):
    return sum(1 for p in img.getdata() if p != (0, 0, 0))


# ---- maze --------------------------------------------------------------------------------


def test_maze_builds_solves_and_restarts():
    mod = MazeModule(make_ctx(Size(32, 32)), MazeSettings(build_speed=600, solve_speed=600, pause_s=0.2), seed=1)
    assert mod.cols == 15 and mod.rows == 15 and mod._phase is Phase.BUILD
    img = run_frames(mod, Size(32, 32), 60)  # 2 s at 600 cells/s: built and solved
    assert mod._phase in (Phase.SHOW, Phase.FADE) or mod.solved
    assert len(mod.visited) == mod.total  # every cell carved
    assert lit(img) > 100
    if mod.solved:
        assert mod.path[0] == mod.start and mod.path[-1] == mod.goal
    first_img = mod._img
    run_frames(mod, Size(32, 32), 60)  # pause + fade elapse and a fresh maze starts
    assert mod._img is not first_img


def test_maze_corridor_width_changes_grid():
    ctx = make_ctx(Size(64, 64))
    fine = MazeModule(ctx, MazeSettings(corridor=1), seed=3)
    chunky = MazeModule(ctx, MazeSettings(corridor=3), seed=3)
    assert fine.cols == 31 and chunky.cols == 15
    img = run_frames(chunky, Size(64, 64), 5)
    assert img.size == (64, 64)


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_maze(size, request):
    mod = MazeModule(make_ctx(size), MazeSettings(build_speed=300, solve_speed=300), seed=42)
    img = run_frames(mod, size, 90)  # 3 s: mid-build or solving depending on size
    assert_golden(img, f"maze/{size}/frame_90", request)


def test_golden_maze_rainbow_solved(request):
    mod = MazeModule(
        make_ctx(Size(64, 64)), MazeSettings(rainbow_walls=True, build_speed=600, solve_speed=600, pause_s=5), seed=7
    )
    img = run_frames(mod, Size(64, 64), 150)
    assert mod.solved
    assert_golden(img, "maze/64x64/rainbow_solved", request)


# ---- qix ----------------------------------------------------------------------------------


def test_qix_moves_and_keeps_trail_bounded():
    mod = QixModule(make_ctx(Size(64, 64)), QixSettings(trail=10, qixes=2), seed=5)
    img = run_frames(mod, Size(64, 64), 90)
    assert all(len(q.lines) == 10 for q in mod.qixes)
    for q in mod.qixes:
        for p in (q.a, q.b):
            assert 0 <= p.x <= 63 and 0 <= p.y <= 63
    assert lit(img) > 20


@pytest.mark.parametrize("mode", ["rainbow", "single", "duo"])
def test_golden_qix_modes(mode, request):
    mod = QixModule(make_ctx(Size(64, 64)), QixSettings(color_mode=mode), seed=11)
    assert_golden(run_frames(mod, Size(64, 64), 60), f"qix/64x64/{mode}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(64, 64)], ids=str)
def test_golden_qix_sizes(size, request):
    mod = QixModule(make_ctx(size), QixSettings(), seed=11)
    img = run_frames(mod, size, 60)
    assert img.size == size.as_tuple()
    assert_golden(img, f"qix/{size}/rainbow", request)
