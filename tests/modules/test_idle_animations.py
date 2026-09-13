from __future__ import annotations

import pytest

from homely.core.module import FrameInfo
from homely.modules.maze.module import Grid, MazeModule, Phase
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


def test_grid_is_a_perfect_maze_with_entrance_and_exit():
    import random

    g = Grid(7, 9, random.Random(3))
    assert not g.right[g.end_row][8]  # exit open on the right edge
    path = g.shortest_path()
    assert path[0] == (g.start_row, 0) and path[-1] == (g.end_row, 8)
    assert all(g.open_between(a, b) for a, b in zip(path, path[1:], strict=False))
    # every cell is reachable (a spanning tree has rows*cols-1 openings)
    openings = sum(not v for row in g.right[:] for v in row[:-1]) + sum(not v for row in g.bottom[:-1] for v in row)
    assert openings == 7 * 9 - 1


def test_maze_draws_walls_then_path_then_restarts():
    mod = MazeModule(make_ctx(Size(64, 64)), MazeSettings(draw_speed=2000, solve_speed=2000, pause_s=0.5), seed=1)
    assert mod._phase is Phase.WALLS and 3 <= mod.grid.cols <= 10 and 3 <= mod.grid.rows <= 10
    first = mod.grid
    img = run_frames(mod, Size(64, 64), 60)  # 2 s at 2000 px/s: walls and path drawn, hold begun
    assert mod._phase is Phase.HOLD or mod.grid is not first
    assert lit(img) > 60
    run_frames(mod, Size(64, 64), 30)  # hold expires -> a new maze has started
    assert mod.grid is not first


def test_maze_sizes_respect_min_cell():
    mod = MazeModule(make_ctx(Size(32, 32)), MazeSettings(min_cell_px=8, min_cells=2), seed=2)
    assert mod.grid.cols <= 4 and mod.grid.rows <= 4 and mod.cell_w >= 8


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_maze(size, request):
    mod = MazeModule(make_ctx(size), MazeSettings(draw_speed=400, solve_speed=400), seed=42)
    img = run_frames(mod, size, 90)  # 3 s in
    assert_golden(img, f"maze/{size}/frame_90", request)


def test_golden_maze_solved(request):
    mod = MazeModule(make_ctx(Size(64, 64)), MazeSettings(draw_speed=2000, solve_speed=2000, pause_s=10), seed=7)
    img = run_frames(mod, Size(64, 64), 60)
    assert mod._phase is Phase.HOLD
    assert_golden(img, "maze/64x64/solved", request)


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
