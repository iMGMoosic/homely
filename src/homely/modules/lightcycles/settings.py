from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class LightCyclesSettings(ModuleSettings):
    cycles: Literal[2, 3, 4] = Field(2, title="Riders", json_schema_extra={"x-group": "Game", "x-order": 10})
    cell_px: Literal[0, 1, 2, 3, 4] = Field(
        0,
        title="Cell size (pixels)",
        description="0 = automatic (1 px on small panels, 2 px on 128-wide)",
        json_schema_extra={"x-group": "Game", "x-order": 20},
    )
    speed: int = Field(
        24,
        ge=4,
        le=80,
        title="Cells per second",
        json_schema_extra={"x-group": "Game", "x-order": 30, "x-widget": "slider"},
    )
    lookahead: int = Field(
        6,
        ge=1,
        le=20,
        title="Reflexes (cells of lookahead)",
        description="How far ahead a rider notices a wall",
        json_schema_extra={"x-group": "Game", "x-order": 40},
    )
    aggression: int = Field(
        45,
        ge=0,
        le=100,
        title="Aggression",
        description="How much a rider will give up space of its own to shut an opponent in. "
        "0 plays solitaire and simply takes the most room it can.",
        json_schema_extra={"x-group": "Game", "x-order": 45, "x-widget": "slider"},
    )
    pause_s: float = Field(
        2.5,
        ge=0,
        le=15,
        title="Pause after the last crash (seconds)",
        json_schema_extra={"x-group": "Game", "x-order": 50},
    )
    grid_glow: bool = Field(True, title="Faint arena grid", json_schema_extra={"x-group": "Look", "x-order": 10})
    palette: Literal["classic", "neon", "duel"] = Field(
        "classic",
        title="Palette",
        description="classic = Tron blue vs orange",
        json_schema_extra={"x-group": "Look", "x-order": 20},
    )
