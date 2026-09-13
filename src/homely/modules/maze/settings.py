from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class MazeSettings(ModuleSettings):
    corridor: Literal[1, 2, 3] = Field(
        1,
        title="Corridor width (pixels)",
        description="1 = a fine maze with many cells; 3 = chunky",
        json_schema_extra={"x-group": "Maze", "x-order": 10},
    )
    build_speed: int = Field(
        60,
        ge=5,
        le=600,
        title="Build speed (cells per second)",
        json_schema_extra={"x-group": "Maze", "x-order": 20, "x-widget": "slider"},
    )
    solve_speed: int = Field(
        40,
        ge=5,
        le=600,
        title="Solve speed (steps per second)",
        json_schema_extra={"x-group": "Maze", "x-order": 30, "x-widget": "slider"},
    )
    pause_s: float = Field(
        2.5,
        ge=0,
        le=15,
        title="Pause on the solved maze (seconds)",
        json_schema_extra={"x-group": "Maze", "x-order": 40},
    )
    wall_color: str = Field(
        "#3060C0",
        title="Walls",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 10},
    )
    explore_color: str = Field(
        "#404048",
        title="Explored dead ends",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
    trail_color: str = Field(
        "#FFB000",
        title="Solver trail",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 30},
    )
    path_color: str = Field(
        "#00FF80",
        title="Solved path",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 40},
    )
    rainbow_walls: bool = Field(
        False,
        title="Rainbow walls",
        description="Color walls by when they were built",
        json_schema_extra={"x-group": "Colors", "x-order": 50},
    )
