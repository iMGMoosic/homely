from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class QixSettings(ModuleSettings):
    trail: int = Field(
        5,
        ge=1,
        le=60,
        title="Trail length (lines)",
        json_schema_extra={"x-group": "Motion", "x-order": 10, "x-widget": "slider"},
    )
    jitter: int = Field(
        8,
        ge=1,
        le=24,
        title="Jitter",
        description="Each endpoint moves a random 1..jitter pixels (times 1-3) per frame",
        json_schema_extra={"x-group": "Motion", "x-order": 20, "x-widget": "slider"},
    )
    qixes: Literal[1, 2, 3] = Field(1, title="Number of qixes", json_schema_extra={"x-group": "Motion", "x-order": 30})
    color_mode: Literal["walk", "rainbow", "single"] = Field(
        "walk",
        title="Colors",
        description="walk = each color channel wanders randomly; rainbow = hue cycle; single = one color",
        json_schema_extra={"x-group": "Colors", "x-order": 10},
    )
    color_step: int = Field(
        8, ge=1, le=64, title="Color walk step", json_schema_extra={"x-group": "Colors", "x-order": 20}
    )
    color: str = Field(
        "#00A8FF",
        title="Color (single)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 30},
    )
    fade_trail: bool = Field(True, title="Fade older lines", json_schema_extra={"x-group": "Colors", "x-order": 40})
