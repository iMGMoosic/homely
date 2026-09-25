from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from homely.core.module import ModuleSettings


class CalendarSource(BaseModel):
    name: str = Field("", title="Name", description="Optional, to tell your calendars apart here")
    url: str = Field(
        title="ICS link",
        description=(
            "The calendar's iCal/ICS address (webcal:// works too). In Google Calendar: Settings → "
            "your calendar → Secret address in iCal format."
        ),
    )
    color: str = Field("#4F9DFF", title="Color", pattern=r"^#[0-9A-Fa-f]{6}$", json_schema_extra={"format": "color"})

    @field_validator("url")
    @classmethod
    def _http(cls, v: str) -> str:
        v = v.strip()
        if v.lower().startswith("webcal://"):
            v = "https://" + v[len("webcal://") :]
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("must start with https://, http:// or webcal://")
        return v


class CalendarSettings(ModuleSettings):
    calendars: list[CalendarSource] = Field(
        default_factory=list,
        title="Calendars",
        json_schema_extra={"x-group": "Calendars", "x-order": 10},
    )
    days_ahead: int = Field(
        7, ge=1, le=31, title="Days ahead", json_schema_extra={"x-group": "Calendars", "x-order": 20}
    )
    refresh_minutes: int = Field(
        15, ge=5, le=240, title="Refresh every (minutes)", json_schema_extra={"x-group": "Calendars", "x-order": 30}
    )
    show_all_day: bool = Field(
        True, title="Show all-day events", json_schema_extra={"x-group": "Calendars", "x-order": 40}
    )
    show_when_empty: bool = Field(
        False,
        title="Take a turn when nothing is coming up",
        description="Off skips the calendar in the rotation while it has no upcoming events",
        json_schema_extra={"x-group": "Calendars", "x-order": 50},
    )
    max_events: int = Field(
        9, ge=1, le=50, title="Events per turn", json_schema_extra={"x-group": "Layout", "x-order": 10}
    )
    seconds_per_page: int = Field(
        6,
        ge=3,
        le=60,
        title="Seconds per page",
        description="Each page shows as many events as fit on the panel",
        json_schema_extra={"x-group": "Layout", "x-order": 20},
    )
    time_format: Literal["12h", "24h"] = Field(
        "12h", title="Time format", json_schema_extra={"x-group": "Layout", "x-order": 30}
    )
    text_color: str = Field(
        "#FFFFFF",
        title="Text color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 10, "format": "color"},
    )
    header_color: str = Field(
        "#FFB000",
        title="Day heading color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 20, "format": "color"},
    )
