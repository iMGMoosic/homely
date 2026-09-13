from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings

DateFormat = Literal["weekday_month_day", "month_day", "day_month", "iso", "none"]


class ClockSettings(ModuleSettings):
    style: Literal["segment", "pixel"] = Field(
        "segment",
        title="Digit style",
        description="segment = seven-segment LCD clock digits; pixel = bitmap font",
        json_schema_extra={"x-group": "Time", "x-order": 5},
    )
    ghost_segments: bool = Field(
        True,
        title="Show unlit segments",
        description="Faint outline of the off segments, like a real LCD",
        json_schema_extra={"x-group": "Time", "x-order": 6},
    )
    time_format: Literal["12h", "24h"] = Field(
        "12h", title="Time format", json_schema_extra={"x-group": "Time", "x-order": 10}
    )
    leading_zero: bool = Field(
        False, title="Leading zero on hour", json_schema_extra={"x-group": "Time", "x-order": 20}
    )
    show_ampm: bool = Field(True, title="Show AM/PM", json_schema_extra={"x-group": "Time", "x-order": 30})
    show_seconds: bool = Field(False, title="Show seconds", json_schema_extra={"x-group": "Time", "x-order": 40})
    blink_colon: bool = Field(True, title="Blink colon", json_schema_extra={"x-group": "Time", "x-order": 50})
    timezone: str | None = Field(
        None,
        title="Timezone override",
        description="IANA name like America/Chicago. Empty uses the global location timezone.",
        json_schema_extra={"x-group": "Time", "x-order": 60, "x-widget": "timezone"},
    )
    date_format: DateFormat = Field(
        "weekday_month_day", title="Date", json_schema_extra={"x-group": "Date", "x-order": 10}
    )
    time_color: str = Field(
        "#FFFFFF",
        title="Time color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "x-order": 10, "format": "color"},
    )
    date_color: str = Field(
        "#FFB000",
        title="Date color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "x-order": 20, "format": "color"},
    )
    accent_color: str = Field(
        "#00A8FF",
        title="Accent color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "x-order": 30, "format": "color"},
    )

    @property
    def show_date(self) -> bool:
        return self.date_format != "none"
