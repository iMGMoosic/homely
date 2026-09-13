from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class QixSettings(ModuleSettings):
    trail: int = Field(
        24,
        ge=2,
        le=120,
        title="Trail length (lines)",
        json_schema_extra={"x-group": "Motion", "x-order": 10, "x-widget": "slider"},
    )
    speed: int = Field(
        40,
        ge=5,
        le=200,
        title="Speed (pixels per second)",
        json_schema_extra={"x-group": "Motion", "x-order": 20, "x-widget": "slider"},
    )
    spawn_rate: int = Field(
        20, ge=2, le=60, title="New line every 1/N second", json_schema_extra={"x-group": "Motion", "x-order": 30}
    )
    qixes: Literal[1, 2, 3] = Field(1, title="Number of qixes", json_schema_extra={"x-group": "Motion", "x-order": 40})
    color_mode: Literal["rainbow", "single", "duo"] = Field(
        "rainbow", title="Colors", json_schema_extra={"x-group": "Colors", "x-order": 10}
    )
    color: str = Field(
        "#00A8FF",
        title="Color (single/duo)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
    color2: str = Field(
        "#FF00C8",
        title="Second color (duo)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 30},
    )
    hue_speed: int = Field(
        6, ge=1, le=120, title="Rainbow cycle (seconds)", json_schema_extra={"x-group": "Colors", "x-order": 40}
    )
    fade_trail: bool = Field(True, title="Fade older lines", json_schema_extra={"x-group": "Colors", "x-order": 50})
