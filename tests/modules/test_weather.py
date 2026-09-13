from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from homely.core.module import FrameInfo
from homely.modules.weather.colors import NIGHT, NOON, SUNRISE, sky_gradient, temp_color
from homely.modules.weather.module import WeatherModule
from homely.modules.weather.providers import Forecast, OpenMeteoProvider
from homely.modules.weather.providers.open_meteo import parse_forecast
from homely.modules.weather.settings import WeatherSettings
from homely.modules.weather.solar import sun_times
from homely.modules.weather.wmo import icon_for, label_for, short_label_for
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import make_ctx
from tests.golden_util import assert_golden

FIXTURE = Path(__file__).parent.parent / "fixtures" / "open_meteo_forecast.json"
CHI = ZoneInfo("America/Chicago")
NOW_DAY = datetime(2026, 9, 13, 14, 30, 0, tzinfo=CHI)
NOW_NIGHT = datetime(2026, 9, 13, 2, 0, 0, tzinfo=CHI)


def fixture_forecast() -> Forecast:
    return parse_forecast(json.loads(FIXTURE.read_text()), "imperial", "Weather data by Open-Meteo.com")


def make_module(
    settings: WeatherSettings, size: Size, now: datetime, forecast: Forecast, name: str | None = "Minneapolis"
):
    ctx = make_ctx(size, now=now)
    if name:
        ctx.location.config.name = name
    mod = WeatherModule(ctx, settings)
    mod.forecast.set(forecast, now)
    return mod


def render(mod: WeatherModule, size: Size, now: datetime, progress: float = 0.0):
    canvas = Canvas(size)
    frame = FrameInfo(now=now, monotonic=100.0, dt=1.0, index=0, slot_elapsed=progress * 20, slot_duration=20)
    mod.render(canvas, frame)
    return canvas.snapshot()


# ---- provider ------------------------------------------------------------------------


def test_parse_fixture():
    fc = fixture_forecast()
    assert fc.current.temp == 53.6 and fc.current.code == 3 and not fc.current.is_day
    assert fc.current.time.tzinfo is not None and fc.current.time.utcoffset() == timedelta(hours=-5)
    assert len(fc.daily) == 5 and fc.daily[0].tmax == 71.5 and fc.daily[1].precip_prob == 100
    assert fc.latitude is not None and abs(fc.latitude - 44.98) < 0.1
    assert fc.daily[0].sunrise is not None and fc.daily[0].sunrise.hour == 6
    assert len(fc.hourly) == 120
    # round-trips through the disk-cache encoding
    again = Forecast.from_dict(json.loads(json.dumps(fc.to_dict())))
    assert again == fc


@pytest.mark.asyncio
async def test_provider_request_params_and_fetch():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=json.loads(FIXTURE.read_text()))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenMeteoProvider(client, forecast_days=4)
        fc = await provider.fetch(44.98, -93.27, "metric", "America/Chicago")
    assert seen["temperature_unit"] == "celsius" and seen["wind_speed_unit"] == "kmh"
    assert seen["forecast_days"] == "4" and seen["timezone"] == "America/Chicago"
    assert "sunrise" in seen["daily"] and "weather_code" in seen["current"]
    assert fc.units == "metric" and fc.attribution.startswith("Weather data by")


# ---- mappings and colors ------------------------------------------------------------------


def test_wmo_mapping():
    assert icon_for(0) == "clear" and label_for(0) == "Sunny" and label_for(0, is_day=False) == "Clear"
    assert icon_for(95) == "thunder" and short_label_for(95) == "Storm"
    assert icon_for(65) == "heavy_rain" and icon_for(66) == "sleet" and icon_for(999) == "cloudy"


def test_temp_color_scale_matches_prototype_palette():
    from homely.render.color import lerp

    assert temp_color(-60) == (228, 240, 255) and temp_color(125) == (61, 2, 22)  # 38 stops, 5 F apart
    assert temp_color(70) == (135, 154, 132) and temp_color(75) == (171, 168, 125)
    assert temp_color(72.5) == lerp((135, 154, 132), (171, 168, 125), 0.5)
    assert temp_color(0, metric=True) == temp_color(32)
    assert temp_color(-100) == temp_color(-60) and temp_color(200) == temp_color(125)
    cold, hot = temp_color(20), temp_color(100)
    assert cold[2] > cold[0] and hot[0] > hot[2]


def test_sky_gradient_phases():
    sun = sun_times(44.98, -93.27, datetime(2026, 9, 13).date(), CHI)
    assert sun.dawn and sun.sunrise and sun.sunset and sun.dusk
    assert sky_gradient(datetime(2026, 9, 13, 2, 0, tzinfo=CHI), sun) == NIGHT
    assert sky_gradient(sun.sunrise, sun) == SUNRISE
    assert sky_gradient(sun.noon, sun) == NOON
    assert sky_gradient(sun.sunset, sun) == SUNRISE
    assert sky_gradient(datetime(2026, 9, 13, 23, 30, tzinfo=CHI), sun) == NIGHT
    mid_dawn = sun.dawn + (sun.sunrise - sun.dawn) / 2
    top, _ = sky_gradient(mid_dawn, sun)
    assert NIGHT[0][0] < top[0] < SUNRISE[0][0]


# ---- module behaviour -------------------------------------------------------------------------


def test_should_display_only_with_data_and_page_flip():
    ctx = make_ctx(Size(64, 64), now=NOW_DAY)
    mod = WeatherModule(ctx, WeatherSettings())
    assert not mod.should_display()
    mod.forecast.set(fixture_forecast(), NOW_DAY)
    assert mod.should_display() and mod.fps() == 1
    first = FrameInfo(now=NOW_DAY, monotonic=0, dt=0, index=0, slot_elapsed=1, slot_duration=20)
    second = FrameInfo(now=NOW_DAY, monotonic=0, dt=0, index=0, slot_elapsed=15, slot_duration=20)
    assert mod._page(first) == "current" and mod._page(second) == "forecast"
    assert mod._page(replace(first, slot_elapsed=19)) == "forecast"
    mod.settings = WeatherSettings(view="current")
    assert mod._page(second) == "current"


@pytest.mark.asyncio
async def test_setup_loads_cache_and_skips_fetch_without_location(tmp_path):
    ctx = make_ctx(Size(64, 64), now=NOW_DAY, tmp=tmp_path)
    ctx._http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    fc = fixture_forecast()
    ctx.cache.set("forecast", {"forecast": fc.to_dict(), "at": NOW_DAY.isoformat()})
    mod = WeatherModule(ctx, WeatherSettings())
    await mod.setup()
    assert mod.forecast.value == fc
    await mod._fetch()  # no lat/lon configured: must not raise, must not change data
    assert mod.forecast.value == fc


# ---- goldens --------------------------------------------------------------------------------------


def variants() -> dict[str, tuple[WeatherSettings, Forecast, datetime]]:
    fc = fixture_forecast()
    sunny = replace(fc, current=replace(fc.current, code=0, is_day=True, temp=78.2, feels_like=81.0))
    storm = replace(fc, current=replace(fc.current, code=95, is_day=True, temp=64.0))
    snow = replace(
        fc,
        current=replace(fc.current, code=73, is_day=True, temp=18.0, feels_like=5.0),
        daily=[replace(fc.daily[0], tmax=22.0, tmin=-3.0), *fc.daily[1:]],
    )
    rainy_hours: list = []
    k = 0
    for h in fc.hourly:
        if h.time >= NOW_DAY.replace(minute=0):
            k += 1
            h = replace(h, precip_prob=min(100, 9 * k))
        rainy_hours.append(h)
    rainy = replace(sunny, hourly=rainy_hours)
    return {
        "night_overcast": (WeatherSettings(), fc, NOW_NIGHT),
        "day_sunny": (WeatherSettings(), sunny, NOW_DAY),
        "day_storm_feels": (WeatherSettings(show_feels_like=True), storm, NOW_DAY),
        "day_snow_cold": (WeatherSettings(), snow, NOW_DAY),
        "plain_no_gradient_no_strip": (WeatherSettings(temperature_gradient=False, sky_strip=False), sunny, NOW_DAY),
        "forecast_page": (WeatherSettings(), rainy, NOW_DAY),
        "forecast_5days_nobars": (WeatherSettings(forecast_days=5, show_precip_bars=False), sunny, NOW_DAY),
    }


@pytest.mark.parametrize("name", list(variants()))
def test_golden_64x64(name, request):
    settings, fc, now = variants()[name]
    mod = make_module(settings, Size(64, 64), now, fc)
    progress = 0.75 if name.startswith("forecast") else 0.0
    assert_golden(render(mod, Size(64, 64), now, progress), f"weather/64x64/{name}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(64, 64)], ids=str)
@pytest.mark.parametrize("page", ["current", "forecast"])
def test_golden_other_sizes(size, page, request):
    settings, fc, now = variants()["forecast_page" if page == "forecast" else "day_sunny"]
    mod = make_module(settings, size, now, fc)
    img = render(mod, size, now, 0.0 if page == "current" else 0.75)
    assert img.size == size.as_tuple()
    assert_golden(img, f"weather/{size}/{page}", request)
