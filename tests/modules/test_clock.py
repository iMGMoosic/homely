from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homely.core.module import FrameInfo
from homely.modules.clock.module import ClockModule
from homely.modules.clock.settings import ClockSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden


def render(settings: ClockSettings, size: Size = Size(64, 64), now: datetime = FROZEN, monotonic: float = 100.0):
    ctx = make_ctx(size, now=now)
    mod = ClockModule(ctx, settings)
    canvas = Canvas(size)
    frame = FrameInfo(now=now, monotonic=monotonic, dt=0.5, index=0, slot_elapsed=0, slot_duration=15)
    mod.render(canvas, frame)
    return canvas.snapshot(), mod


CASES = {
    "12h_default": ClockSettings(),
    "12h_seconds": ClockSettings(show_seconds=True),
    "12h_seconds_noghost": ClockSettings(show_seconds=True, ghost_segments=False),
    "24h_seconds_iso": ClockSettings(time_format="24h", show_seconds=True, date_format="iso"),
    "24h_nodate": ClockSettings(time_format="24h", date_format="none", blink_colon=False),
    "12h_noampm_daymonth": ClockSettings(show_ampm=False, date_format="day_month"),
    "pixel_12h_seconds": ClockSettings(style="pixel", show_seconds=True),
    "pixel_24h": ClockSettings(style="pixel", time_format="24h"),
}


@pytest.mark.parametrize("name", list(CASES))
def test_golden_64x64(name, request):
    img, _ = render(CASES[name])
    assert_golden(img, f"clock/64x64/{name}", request)


def test_golden_leading_zero_and_colon_off(request):
    now = datetime(2026, 9, 12, 9, 5, 0, tzinfo=ZoneInfo("America/Chicago"))
    img, _ = render(ClockSettings(leading_zero=True), now=now, monotonic=100.5)  # odd half-second: colon hidden
    assert_golden(img, "clock/64x64/0905_colon_off", request)
    img2, _ = render(ClockSettings(), now=now, monotonic=100.0)
    assert_golden(img2, "clock/64x64/905_colon_on", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(64, 64)], ids=str)
@pytest.mark.parametrize("style", ["segment", "pixel"])
def test_golden_other_sizes(size, style, request):
    img, _ = render(ClockSettings(show_seconds=True, style=style), size=size)
    assert img.size == size.as_tuple()
    assert_golden(img, f"clock/{size}/{style}_12h_seconds", request)


@pytest.mark.parametrize("style", ["segment", "pixel"])
def test_128x32_uses_more_than_the_middle_64_pixels(style):
    """A 128x32 panel is not an even multiple of the 64x32 layout, so without one of its own
    the clock is drawn into the middle 64 columns and the rest of the board stays dark."""
    size = Size(128, 32)
    img, _ = render(ClockSettings(style=style, show_seconds=True), size=size)
    lit_x = [x for x in range(size.w) for y in range(size.h) if img.getpixel((x, y)) != (0, 0, 0)]
    assert max(lit_x) - min(lit_x) > 64
    margin = (size.w - 64) // 2  # where a centred 64-wide layout would have stopped
    assert min(lit_x) < margin or max(lit_x) >= size.w - margin


def test_helpers_and_fps():
    _, mod = render(ClockSettings())
    assert mod.fps() == 2
    _, mod = render(ClockSettings(blink_colon=False, show_seconds=False))
    assert mod.fps() == 1
    now = datetime(2026, 9, 12, 0, 7, tzinfo=ZoneInfo("UTC"))
    _, mod = render(ClockSettings(time_format="12h"), now=now)
    assert mod.hour_text(now) == "12" and mod.ampm(now) == "AM"
    assert mod.time_digits(now) == "12:07"
    nine = datetime(2026, 9, 12, 9, 5, tzinfo=ZoneInfo("UTC"))
    assert mod.time_digits(nine) == " 9:05" and mod.hour_text(nine) == "9"
    _, mod = render(ClockSettings(time_format="24h"), now=now)
    assert mod.hour_text(now) == "00" and mod.ampm(now) == ""
    assert mod.date_text(now) == "Sat Sep 12"


def test_timezone_override_applies():
    now = datetime(2026, 9, 12, 13, 0, tzinfo=ZoneInfo("America/Chicago"))
    _, mod = render(ClockSettings(timezone="Europe/London", time_format="24h"), now=now)
    frame = FrameInfo(now=now, monotonic=0, dt=0, index=0, slot_elapsed=0, slot_duration=1)
    assert mod.now(frame).hour == 19


def test_settings_schema_has_ui_hints():
    schema = ClockSettings.model_json_schema()
    assert schema["properties"]["time_color"]["format"] == "color"
    assert schema["properties"]["time_format"]["x-group"] == "Time"
    assert schema["additionalProperties"] is False
