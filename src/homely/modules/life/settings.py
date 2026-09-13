from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class LifeSettings(ModuleSettings):
    cell_px: Literal[0, 1, 2, 3, 4] = Field(
        0,
        title="Cell size (pixels)",
        description="0 = automatic (1 px on small panels, 2 px on 128-wide)",
        json_schema_extra={"x-group": "Life", "x-order": 10},
    )
    generations_per_second: int = Field(
        8,
        ge=1,
        le=30,
        title="Generations per second",
        json_schema_extra={"x-group": "Life", "x-order": 20, "x-widget": "slider"},
    )
    density: int = Field(
        30,
        ge=5,
        le=70,
        title="Initial soup density (%)",
        json_schema_extra={"x-group": "Life", "x-order": 30, "x-widget": "slider"},
    )
    wrap: bool = Field(True, title="Wrap around the edges", json_schema_extra={"x-group": "Life", "x-order": 40})
    stall_generations: int = Field(
        40,
        ge=5,
        le=500,
        title="Reseed after this many repeating generations",
        json_schema_extra={"x-group": "Life", "x-order": 50},
    )
    color_mode: Literal["age", "single", "rainbow"] = Field(
        "age",
        title="Cell colors",
        description="age = newborn cells are white and settle into the color",
        json_schema_extra={"x-group": "Colors", "x-order": 10},
    )
    color: str = Field(
        "#00E08C",
        title="Cell color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
    trails: bool = Field(
        True, title="Ghost trails where cells died", json_schema_extra={"x-group": "Colors", "x-order": 30}
    )
