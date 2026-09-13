from __future__ import annotations

from pydantic import Field

from homely.core.module import ModuleSettings


class TreeSettings(ModuleSettings):
    speed: int = Field(
        10,
        ge=1,
        le=60,
        title="Growth steps per second",
        json_schema_extra={"x-group": "Tree", "x-order": 10, "x-widget": "slider"},
    )
    seasons: bool = Field(
        True,
        title="Seasons",
        description="Leaves turn and fall before the next tree",
        json_schema_extra={"x-group": "Tree", "x-order": 20},
    )
    hold_s: float = Field(
        4.0, ge=0, le=30, title="Hold the full tree (seconds)", json_schema_extra={"x-group": "Tree", "x-order": 30}
    )
    trunk_color: str = Field(
        "#6B4226",
        title="Trunk",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 10},
    )
    leaf_color: str = Field(
        "#3CB043",
        title="Leaves",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
    autumn_color: str = Field(
        "#E8701A",
        title="Autumn leaves",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 30},
    )
