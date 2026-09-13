from __future__ import annotations

from pydantic import Field

from homely.core.module import ModuleSettings


class MazeSettings(ModuleSettings):
    min_cell_px: int = Field(
        6,
        ge=3,
        le=32,
        title="Smallest cell (pixels)",
        description="Each round picks a random maze size; cells are at least this big",
        json_schema_extra={"x-group": "Maze", "x-order": 10},
    )
    min_cells: int = Field(
        3, ge=2, le=20, title="Fewest cells per side", json_schema_extra={"x-group": "Maze", "x-order": 20}
    )
    draw_speed: int = Field(
        120,
        ge=10,
        le=2000,
        title="Wall drawing speed (pixels per second)",
        json_schema_extra={"x-group": "Maze", "x-order": 30, "x-widget": "slider"},
    )
    solve_speed: int = Field(
        90,
        ge=10,
        le=2000,
        title="Path drawing speed (pixels per second)",
        json_schema_extra={"x-group": "Maze", "x-order": 40, "x-widget": "slider"},
    )
    pause_s: float = Field(
        5.0,
        ge=0,
        le=30,
        title="Pause on the solved maze (seconds)",
        json_schema_extra={"x-group": "Maze", "x-order": 50},
    )
    wall_color: str = Field(
        "#FF0000",
        title="Walls",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 10},
    )
    path_color: str = Field(
        "#00FF00",
        title="Solution path",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
