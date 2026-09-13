from __future__ import annotations

import pytest

from homely.core.module import FrameInfo
from homely.modules.lavalamp.module import LavaLampModule
from homely.modules.lavalamp.settings import LavaLampSettings
from homely.modules.life.module import LifeModule
from homely.modules.life.settings import LifeSettings
from homely.modules.tvstatic.module import Mode, TvStaticModule
from homely.modules.tvstatic.settings import TvStaticSettings
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


# ---- life ---------------------------------------------------------------------------------


def test_life_blinker_oscillates_and_glider_moves():
    from PIL import Image

    mod = LifeModule(make_ctx(Size(16, 16)), LifeSettings(cell_px=1, wrap=False), seed=1)
    board = Image.new("L", (16, 16), 0)
    for x in (6, 7, 8):
        board.putpixel((x, 8), 1)  # blinker
    mod.alive = board
    mod.step()
    assert [mod.alive.getpixel((7, y)) for y in (7, 8, 9)] == [1, 1, 1] and mod.alive.getpixel((6, 8)) == 0
    mod.step()
    assert [mod.alive.getpixel((x, 8)) for x in (6, 7, 8)] == [1, 1, 1]
    # a glider travels one cell diagonally every four generations
    board = Image.new("L", (16, 16), 0)
    for x, y in ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2)):
        board.putpixel((x, y), 1)
    mod.alive = board
    for _ in range(4):
        mod.step()
    assert {(x, y) for x in range(16) for y in range(16) if mod.alive.getpixel((x, y))} == {
        (2, 1),
        (3, 2),
        (1, 3),
        (2, 3),
        (3, 3),
    }
    assert mod.population == 5


def test_life_wraps_and_reseeds_when_stalled():
    from PIL import Image

    mod = LifeModule(
        make_ctx(Size(8, 8)), LifeSettings(cell_px=1, wrap=True, stall_generations=5, generations_per_second=30), seed=2
    )
    board = Image.new("L", (8, 8), 0)
    for x in (7, 0, 1):
        board.putpixel((x, 4), 1)  # blinker across the wrap seam
    mod.alive = board
    mod.step()
    assert mod.alive.getpixel((0, 3)) == 1 and mod.alive.getpixel((0, 5)) == 1
    # a stable block stalls, then the soup reseeds (fade restarts from 0)
    board = Image.new("L", (8, 8), 0)
    for x, y in ((3, 3), (4, 3), (3, 4), (4, 4)):
        board.putpixel((x, y), 1)
    mod.alive = board
    run_frames(mod, Size(8, 8), 20)
    assert mod._fade < 1.0 or mod.population != 4


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_life(size, request):
    mod = LifeModule(make_ctx(size), LifeSettings(), seed=42)
    assert_golden(run_frames(mod, size, 45), f"life/{size}/frame_45", request)


def test_golden_life_modes(request):
    for mode in ("single", "rainbow"):
        mod = LifeModule(make_ctx(Size(64, 64)), LifeSettings(color_mode=mode, trails=False), seed=42)
        assert_golden(run_frames(mod, Size(64, 64), 45), f"life/64x64/{mode}", request)


# ---- lava lamp -------------------------------------------------------------------------------


def test_lava_blobs_stay_on_screen():
    mod = LavaLampModule(make_ctx(Size(64, 64)), LavaLampSettings(blobs=4, speed=100), seed=3)
    img = run_frames(mod, Size(64, 64), 120)
    for b in mod.blobs:
        assert 0 <= b.x <= 64 and -b.radius <= b.y <= 64 + b.radius
    assert lit(img) == 64 * 64  # background is never pure black


@pytest.mark.parametrize("palette", ["classic", "ocean", "toxic", "sunset"])
def test_golden_lava_palettes(palette, request):
    mod = LavaLampModule(make_ctx(Size(64, 64)), LavaLampSettings(palette=palette), seed=5)
    assert_golden(run_frames(mod, Size(64, 64), 30), f"lavalamp/64x64/{palette}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(64, 64)], ids=str)
def test_golden_lava_sizes(size, request):
    mod = LavaLampModule(make_ctx(size), LavaLampSettings(), seed=5)
    assert_golden(run_frames(mod, size, 30), f"lavalamp/{size}/classic", request)


# ---- tv static -------------------------------------------------------------------------------


def test_static_flips_channels_and_returns():
    mod = TvStaticModule(make_ctx(Size(64, 64)), TvStaticSettings(flip_every_s=2, channel_hold_s=0.5), seed=6)
    seen = set()
    canvas = Canvas(Size(64, 64))
    for i in range(240):  # 8 s
        canvas.clear()
        mod.render(canvas, frame(1 / 30, i / 30))
        seen.add(mod.mode)
    assert seen == {Mode.STATIC, Mode.CHANNEL, Mode.TEAR}


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_static(size, request):
    mod = TvStaticModule(make_ctx(size), TvStaticSettings(channel_flips=False), seed=7)
    assert_golden(run_frames(mod, size, 10), f"tvstatic/{size}/snow", request)


@pytest.mark.parametrize("channel", [0, 1, 2, 3])
def test_golden_static_channels(channel, request):
    mod = TvStaticModule(make_ctx(Size(64, 64)), TvStaticSettings(), seed=7)
    mod.mode, mod.channel, mod.timer = Mode.CHANNEL, channel, 1.0
    mod.settings = TvStaticSettings(channel_hold_s=10)
    assert_golden(run_frames(mod, Size(64, 64), 1), f"tvstatic/64x64/channel_{channel}", request)
