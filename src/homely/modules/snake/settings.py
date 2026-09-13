from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class SnakeSettings(ModuleSettings):
    cell_px: Literal[0, 2, 3, 4, 6, 8] = Field(
        0,
        title="Cell size (pixels)",
        description="0 = automatic (2 px on small panels, 4 px on 128-wide)",
        json_schema_extra={"x-group": "Game", "x-order": 10},
    )
    speed: int = Field(
        12,
        ge=2,
        le=40,
        title="Moves per second",
        json_schema_extra={"x-group": "Game", "x-order": 20, "x-widget": "slider"},
    )
    start_length: int = Field(
        4, ge=2, le=20, title="Starting length", json_schema_extra={"x-group": "Game", "x-order": 30}
    )
    pause_s: float = Field(
        2.0, ge=0, le=15, title="Pause after game over (seconds)", json_schema_extra={"x-group": "Game", "x-order": 40}
    )
    head_color: str = Field(
        "#FFFFFF",
        title="Head",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 10},
    )
    body_color: str = Field(
        "#00D060",
        title="Body",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
    food_color: str = Field(
        "#FF3030",
        title="Food",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 30},
    )
