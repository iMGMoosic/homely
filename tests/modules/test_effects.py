from __future__ import annotations

import itertools

import pytest

from homely.core.module import FrameInfo
from homely.modules.lavalamp.module import DEPART_GAP, LavaLampModule
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


def _lava_run(size: Size, seconds: float, **settings):
    """Run a fresh lava turn, yielding (time, module) after every frame."""
    mod = LavaLampModule(make_ctx(size), LavaLampSettings(**settings), seed=3)
    mod.on_enter()
    canvas = Canvas(size)
    for i in range(int(seconds * 30)):
        canvas.clear()
        mod.render(canvas, frame(1 / 30 if i else 0.0, i / 30))
        yield i / 30, mod


def test_lava_starts_as_one_central_lump_at_the_bottom():
    size = Size(64, 64)
    _, mod = next(_lava_run(size, 0.1))
    assert all(b.resting for b in mod.blobs)
    assert all(b.y > size.h * 0.7 for b in mod.blobs), [b.y for b in mod.blobs]
    xs = [b.x for b in mod.blobs]
    assert max(xs) - min(xs) <= size.w * 0.45
    assert abs(sum(xs) / len(xs) - size.w / 2) < size.w * 0.1  # centred, not off at one side


@pytest.mark.parametrize("size", [Size(64, 64), Size(128, 32)], ids=str)
def test_lava_lump_never_empties_and_blobs_leave_one_at_a_time(size):
    """A real lamp keeps a mass at the bottom that blobs break away from and fall back into;
    they do not all lift off together."""
    departures: list[float] = []
    prev: list[bool] | None = None
    for t, mod in _lava_run(size, 90):
        now = [b.resting for b in mod.blobs]
        assert sum(now) >= len(now) - mod._max_travelling >= 1, t
        if prev is not None:
            departures += [t for was, is_ in zip(prev, now, strict=True) if was and not is_]
        prev = now
    assert len(departures) >= 8  # the loop keeps running the whole turn
    gaps = [b - a for a, b in itertools.pairwise(departures)]
    assert min(gaps) >= DEPART_GAP[0] - 0.05, gaps


@pytest.mark.parametrize("size", [Size(64, 64), Size(128, 32)], ids=str)
def test_lava_lump_stays_one_mass_as_blobs_come_and_go(size):
    """With fixed places, the blobs left at home could be the two ends of the lump -- too far
    apart to merge, so the lump vanished. They should close ranks instead."""
    frames = spread_out = 0
    for t, mod in _lava_run(size, 90):
        home = sorted((b for b in mod.blobs if b.resting), key=lambda b: b.home_x)
        if t < 1 or len(home) < 2:
            continue
        frames += 1
        if any(b.home_x - a.home_x > 2 * min(a.radius, b.radius) for a, b in itertools.pairwise(home)):
            spread_out += 1  # allowed briefly, while the lump makes room for a returning blob
    assert spread_out / frames < 0.1, (spread_out, frames)


def test_lava_circulates_up_one_side_and_down_the_other_then_rejoins_the_lump():
    """A lava lamp is a convection loop, not each blob bobbing on its own sine wave."""
    size = Size(64, 64)
    track: list[tuple[float, float, bool]] = []
    mod = None
    for _, mod in _lava_run(size, 60, blobs=4, speed=100):
        blob = mod.blobs[0]
        track.append((blob.x, blob.y, blob.resting))
    assert mod is not None
    up_x = mod._left if mod._rising_left else mod._right
    down_x = mod._right if mod._rising_left else mod._left
    moving = [(x, y) for x, y, resting in track if not resting]
    climbing = [x for (_, prev_y), (x, y) in itertools.pairwise(moving) if y < prev_y - 0.05]
    sinking = [x for (_, prev_y), (x, y) in itertools.pairwise(moving) if y > prev_y + 0.05]
    assert climbing and sinking
    assert abs(sum(climbing) / len(climbing) - up_x) < abs(sum(climbing) / len(climbing) - down_x)
    assert abs(sum(sinking) / len(sinking) - down_x) < abs(sum(sinking) / len(sinking) - up_x)
    # It went all the way round, and it came home: there is a stretch in the lump after a trip.
    ys = [y for _, y, _ in track]
    assert max(ys) - min(ys) > size.h * 0.5
    states = [resting for *_, resting in track]
    assert any(not a and b for a, b in itertools.pairwise(states))


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
