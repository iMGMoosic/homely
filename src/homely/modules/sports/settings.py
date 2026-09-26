from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from homely.core.module import ModuleSettings


def _league(title: str, default: bool, order: int) -> bool:
    return Field(default, title=title, json_schema_extra={"x-group": "Leagues", "x-order": order})


class SportsSettings(ModuleSettings):
    mlb: bool = _league("MLB", True, 10)
    nfl: bool = _league("NFL", True, 20)
    nba: bool = _league("NBA", True, 30)
    wnba: bool = _league("WNBA", False, 40)
    nhl: bool = _league("NHL", True, 50)
    mls: bool = _league("MLS", False, 60)
    epl: bool = _league("Premier League", False, 70)
    favorites: list[str] = Field(
        default_factory=list,
        title="Favorite teams",
        description=(
            "Team abbreviations or names, e.g. MIN or Twins. MIN matches every Minnesota team in the "
            "leagues above; write nhl:MIN to mean just one league."
        ),
        json_schema_extra={"x-group": "Games", "x-order": 10, "x-placeholder": "e.g. MIN"},
    )
    show: Literal["favorites_first", "favorites_only", "all"] = Field(
        "favorites_first",
        title="Which games",
        description="favorites_only skips the turn on days your teams do not play",
        json_schema_extra={"x-group": "Games", "x-order": 20},
    )
    show_upcoming: bool = Field(
        True, title="Show games not started yet", json_schema_extra={"x-group": "Games", "x-order": 30}
    )
    show_finals: bool = Field(True, title="Show final scores", json_schema_extra={"x-group": "Games", "x-order": 40})
    max_games: int = Field(
        8, ge=1, le=30, title="Games per turn", json_schema_extra={"x-group": "Games", "x-order": 50}
    )
    seconds_per_page: int = Field(
        6,
        ge=3,
        le=30,
        title="Seconds per page",
        description="Each page shows as many games as fit on the panel",
        json_schema_extra={"x-group": "Games", "x-order": 60},
    )
    refresh_minutes: int = Field(
        10,
        ge=2,
        le=60,
        title="Refresh every (minutes)",
        description="While a game you would see is live or about to start, scores refresh every 30 seconds",
        json_schema_extra={"x-group": "Games", "x-order": 70},
    )
    time_format: Literal["12h", "24h"] = Field(
        "12h", title="Time format", json_schema_extra={"x-group": "Look", "x-order": 10}
    )
    team_backgrounds: Literal["translucent", "solid", "off"] = Field(
        "translucent",
        title="Team color backgrounds",
        description=(
            "translucent = the team's band color at 30% behind its text and bar colors; solid = the "
            "band at full strength; off = names on black beside a color bar"
        ),
        json_schema_extra={"x-group": "Look", "x-order": 20},
    )
    text_color: str = Field(
        "#FFFFFF",
        title="Text color",
        description="For the status line, and team names when team backgrounds are off",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Look", "x-order": 30, "format": "color"},
    )

    @field_validator("team_backgrounds", mode="before")
    @classmethod
    def _was_bool(cls, v: object) -> object:
        # 0.3.0 had an on/off switch here; on meant the tinted look.
        if isinstance(v, bool):
            return "translucent" if v else "off"
        return v

    @field_validator("favorites")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        return [f.strip() for f in v if f.strip()]

    def leagues(self) -> list[str]:
        return [k for k in ("mlb", "nfl", "nba", "wnba", "nhl", "mls", "epl") if getattr(self, k)]
