from __future__ import annotations

import math

import pytest

from homely.core.module import FrameInfo
from homely.modules.starfield.module import StarfieldModule
from homely.modules.starfield.settings import StarfieldSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from homely.render.three import (
    Camera,
    DepthBuffer,
    Mesh,
    draw_mesh,
    draw_wireframe,
    m_apply,
    m_mul,
    m_rot_y,
    m_translate,
)
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


# ---- renderer -----------------------------------------------------------------------------


def test_projection_and_transforms():
    cam = Camera(64, 64, focal=32)
    assert cam.project((0, 0, 2)) == (32.0, 32.0, 2)
    assert cam.project((1, 0, 2)) == (48.0, 32.0, 2)  # +x goes right
    assert cam.project((0, 1, 2)) == (32.0, 16.0, 2)  # +y goes up
    assert cam.project((0, 0, -1)) is None
    m = m_mul(m_translate(0, 0, 5), m_rot_y(math.pi / 2))
    x, y, z = m_apply(m, (1, 0, 0))
    assert abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z - 4) < 1e-9


def test_wireframe_and_shaded_cube_draw_something(request):
    cam = Camera(64, 64, focal=48)
    c = Canvas(Size(64, 64))
    m = m_mul(m_translate(0, 0, 3), m_rot_y(0.5))
    draw_wireframe(c, cam, Mesh.cube(1.2), m, (255, 255, 255))
    wire = lit(c.snapshot())
    c.clear()
    draw_mesh(c, cam, Mesh.torus(0.9, 0.35), m, (255, 120, 40))
    assert wire > 20 and lit(c.snapshot()) > wire
    assert_golden(c.snapshot(), "three/64x64/torus", request)


def test_depth_buffer_keeps_nearer_polygon():
    c = Canvas(Size(16, 16))
    db = DepthBuffer(16, 16)
    db.fill_polygon(c, [(2, 2, 5.0), (13, 2, 5.0), (13, 13, 5.0), (2, 13, 5.0)], (255, 0, 0))
    db.fill_polygon(c, [(2, 2, 9.0), (13, 2, 9.0), (13, 13, 9.0), (2, 13, 9.0)], (0, 0, 255))  # farther: hidden
    db.fill_polygon(c, [(6, 6, 1.0), (9, 6, 1.0), (9, 9, 1.0), (6, 9, 1.0)], (0, 255, 0))  # nearer: shows
    img = c.snapshot()
    assert img.getpixel((3, 3)) == (255, 0, 0) and img.getpixel((7, 7)) == (0, 255, 0)


# ---- starfield ------------------------------------------------------------------------------


def test_starfield_recycles_stars_and_draws():
    mod = StarfieldModule(make_ctx(Size(64, 64)), StarfieldSettings(stars=50, speed=200), seed=3)
    img = run_frames(mod, Size(64, 64), 60)
    assert len(mod.stars) == 50 and all(0 < s.z <= 40.0 for s in mod.stars)
    assert lit(img) > 20


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_golden_starfield(size, request):
    mod = StarfieldModule(make_ctx(size), StarfieldSettings(), seed=42)
    assert_golden(run_frames(mod, size, 45), f"starfield/{size}/frame_45", request)
