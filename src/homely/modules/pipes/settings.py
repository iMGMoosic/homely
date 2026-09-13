from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class PipesSettings(ModuleSettings):
    grid: int = Field(
        8, ge=4, le=14, title="Grid size (cells per side)", json_schema_extra={"x-group": "Pipes", "x-order": 10}
    )
    pipes: int = Field(6, ge=1, le=12, title="Pipes per round", json_schema_extra={"x-group": "Pipes", "x-order": 20})
    speed: int = Field(
        6,
        ge=1,
        le=40,
        title="Growth speed (cells per second)",
        json_schema_extra={"x-group": "Pipes", "x-order": 30, "x-widget": "slider"},
    )
    turn_chance: int = Field(
        30,
        ge=0,
        le=100,
        title="Turn chance (%)",
        json_schema_extra={"x-group": "Pipes", "x-order": 40, "x-widget": "slider"},
    )
    pause_s: float = Field(
        4.0, ge=0, le=30, title="Pause when done (seconds)", json_schema_extra={"x-group": "Pipes", "x-order": 50}
    )
    palette: Literal["classic", "warm", "cool", "mono"] = Field(
        "classic", title="Palette", json_schema_extra={"x-group": "Colors", "x-order": 10}
    )
    joints: bool = Field(True, title="Ball joints at corners", json_schema_extra={"x-group": "Colors", "x-order": 20})
