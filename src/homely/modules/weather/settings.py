from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class WeatherSettings(ModuleSettings):
    provider: Literal["open_meteo"] = Field(
        "open_meteo",
        title="Provider",
        description="Open-Meteo is free and needs no API key (data CC BY 4.0)",
        json_schema_extra={"x-group": "Data", "x-order": 10},
    )
    refresh_minutes: int = Field(
        15, ge=5, le=180, title="Refresh every (minutes)", json_schema_extra={"x-group": "Data", "x-order": 20}
    )
    view: Literal["both", "current", "forecast"] = Field(
        "both",
        title="View",
        description="both = current conditions for the first half, then the daily forecast",
        json_schema_extra={"x-group": "Layout", "x-order": 10},
    )
    forecast_days: int = Field(
        3, ge=1, le=5, title="Forecast days", json_schema_extra={"x-group": "Layout", "x-order": 20}
    )
    show_condition: bool = Field(
        True, title="Show condition text", json_schema_extra={"x-group": "Layout", "x-order": 30}
    )
    show_feels_like: bool = Field(
        False, title="Show feels-like temperature", json_schema_extra={"x-group": "Layout", "x-order": 40}
    )
    show_place: bool = Field(
        True,
        title="Show place name",
        description="Uses the name from the global location settings",
        json_schema_extra={"x-group": "Layout", "x-order": 50},
    )
    show_precip_bars: bool = Field(
        True,
        title="Hourly rain chance bars",
        description="On the forecast view: chance of precipitation for the next 12 hours",
        json_schema_extra={"x-group": "Layout", "x-order": 60},
    )
    temperature_gradient: bool = Field(
        True,
        title="Temperature gradient background",
        description="Top = today's high, bottom = today's low, colored by temperature",
        json_schema_extra={"x-group": "Look", "x-order": 10},
    )
    background_brightness: int = Field(
        35,
        ge=5,
        le=100,
        title="Background brightness (%)",
        json_schema_extra={"x-group": "Look", "x-order": 20, "x-widget": "slider"},
    )
    sky_strip: bool = Field(
        True,
        title="Sky strip",
        description="A strip on the right edge showing the sky color over the day, with a marker at now",
        json_schema_extra={"x-group": "Look", "x-order": 30},
    )
    text_color: str = Field(
        "#FFFFFF",
        title="Text color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 40, "format": "color"},
    )
