from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class SkylineSettings(ModuleSettings):
    mode: Literal["timelapse", "realtime"] = Field(
        "timelapse",
        title="Clock",
        description="timelapse = a whole day passes during the turn, starting now; realtime = matches the real sky",
        json_schema_extra={"x-group": "Sky", "x-order": 10},
    )
    day_length_s: int = Field(
        120, ge=20, le=900, title="Timelapse day length (seconds)", json_schema_extra={"x-group": "Sky", "x-order": 20}
    )
    stars: bool = Field(True, title="Stars at night", json_schema_extra={"x-group": "Sky", "x-order": 30})
    traffic: bool = Field(True, title="Cars on the street", json_schema_extra={"x-group": "City", "x-order": 10})
    density: int = Field(
        60,
        ge=20,
        le=100,
        title="Building density (%)",
        json_schema_extra={"x-group": "City", "x-order": 20, "x-widget": "slider"},
    )
    window_color: str = Field(
        "#FFD070",
        title="Lit windows",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "City", "format": "color", "x-order": 30},
    )
