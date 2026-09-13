from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class StarfieldSettings(ModuleSettings):
    stars: int = Field(
        90, ge=10, le=400, title="Stars", json_schema_extra={"x-group": "Motion", "x-order": 10, "x-widget": "slider"}
    )
    speed: int = Field(
        40,
        ge=5,
        le=200,
        title="Speed",
        description="How fast you fly through the field",
        json_schema_extra={"x-group": "Motion", "x-order": 20, "x-widget": "slider"},
    )
    trails: bool = Field(
        True,
        title="Warp trails",
        description="Stars streak as they pass",
        json_schema_extra={"x-group": "Motion", "x-order": 30},
    )
    shooting_stars: bool = Field(True, title="Shooting stars", json_schema_extra={"x-group": "Motion", "x-order": 40})
    color_mode: Literal["white", "tinted", "rainbow"] = Field(
        "tinted",
        title="Star colors",
        description="tinted = mostly white with pastel hints",
        json_schema_extra={"x-group": "Colors", "x-order": 10},
    )
