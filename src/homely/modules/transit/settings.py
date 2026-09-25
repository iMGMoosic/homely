from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from homely.core.module import ModuleSettings


class TransitSettings(ModuleSettings):
    provider: Literal["metro_transit"] = Field(
        "metro_transit",
        title="Agency",
        description="Metro Transit (Minneapolis-St Paul) real-time NexTrip data; no API key needed",
        json_schema_extra={"x-group": "Stop", "x-order": 10},
    )
    stop_id: int | None = Field(
        None,
        ge=1,
        title="Stop number",
        description="The number on the stop sign, or find it by route below",
        json_schema_extra={
            "x-group": "Stop",
            "x-order": 20,
            "x-widget": "transit-stop",
            "x-options": {"provider": "metro_transit"},
        },
    )
    name: str = Field(
        "",
        max_length=40,
        title="Label",
        description="Shown above the departures; empty uses the stop's own name",
        json_schema_extra={"x-group": "Stop", "x-order": 30, "x-placeholder": "e.g. Home"},
    )
    routes: list[str] = Field(
        default_factory=list,
        title="Only these routes",
        description="Route names or numbers, e.g. Blue or 2. Empty shows every route at the stop.",
        json_schema_extra={"x-group": "Stop", "x-order": 40, "x-placeholder": "Add a route"},
    )
    walk_minutes: int = Field(
        0,
        ge=0,
        le=60,
        title="Minutes to walk to the stop",
        description="Departures leaving sooner than this are hidden: you would not make them",
        json_schema_extra={"x-group": "Stop", "x-order": 50},
    )
    max_minutes: int = Field(
        90,
        ge=10,
        le=240,
        title="Look ahead (minutes)",
        description="Departures further away than this are not shown; with none left the turn is skipped",
        json_schema_extra={"x-group": "Stop", "x-order": 60},
    )
    refresh_seconds: int = Field(
        30, ge=15, le=300, title="Refresh every (seconds)", json_schema_extra={"x-group": "Stop", "x-order": 70}
    )
    group_by_route: bool = Field(
        True,
        title="One row per route",
        description="A row per route and direction with its next few times, instead of a row per departure",
        json_schema_extra={"x-group": "Layout", "x-order": 10},
    )
    show_header: bool = Field(True, title="Show the stop name", json_schema_extra={"x-group": "Layout", "x-order": 20})
    show_alerts: bool = Field(
        False,
        title="Scroll service alerts",
        description="Use the bottom row for the agency's alerts at this stop (elevator outages and the like)",
        json_schema_extra={"x-group": "Layout", "x-order": 30},
    )
    time_format: Literal["12h", "24h"] = Field(
        "12h",
        title="Time format",
        description="For timetable departures, which show a clock time rather than a countdown",
        json_schema_extra={"x-group": "Layout", "x-order": 40},
    )
    text_color: str = Field(
        "#FFFFFF",
        title="Text color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 10, "format": "color"},
    )
    header_color: str = Field(
        "#FFC425",
        title="Stop name color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 20, "format": "color"},
    )
    bus_color: str = Field(
        "#2A63B8",
        title="Bus route badge color",
        description="Rail and rapid bus lines use their own line colors",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 30, "format": "color"},
    )

    @field_validator("routes")
    @classmethod
    def _clean_routes(cls, v: list[str]) -> list[str]:
        return [r.strip() for r in v if r.strip()]
