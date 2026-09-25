"""Provider-neutral scoreboard model."""

from __future__ import annotations

import colorsys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol

State = Literal["pre", "live", "final", "off"]  # off = postponed, suspended, cancelled


@dataclass(frozen=True)
class Team:
    abbr: str
    name: str  # short name riders of the bus would say: "Twins", "Wild"
    score: int | None
    color: str = ""  # hex without '#', may be empty
    alt_color: str = ""


@dataclass(frozen=True)
class Game:
    league: str  # key in LEAGUES
    id: str
    start: datetime  # timezone-aware
    state: State
    away: Team
    home: Team
    status: str = ""  # short status for live/final/off games: "Q3 5:32", "P2 INT", "FINAL/OT", "PPD"
    # Baseball extras, filled only for live MLB games.
    inning: int | None = None
    top: bool | None = None
    outs: int | None = None
    bases: tuple[bool, bool, bool] | None = None  # first, second, third

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Game:
        bases = d.get("bases")
        return cls(
            league=d["league"],
            id=str(d["id"]),
            start=datetime.fromisoformat(d["start"]),
            state=d["state"],
            away=Team(**d["away"]),
            home=Team(**d["home"]),
            status=d.get("status", ""),
            inning=d.get("inning"),
            top=d.get("top"),
            outs=d.get("outs"),
            bases=(bool(bases[0]), bool(bases[1]), bool(bases[2])) if bases else None,
        )

    def teams(self) -> tuple[Team, Team]:
        return (self.away, self.home)


class SportsProvider(Protocol):
    async def games(self, day: date) -> list[Game]: ...


def to_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def team_color(primary: str, alternate: str) -> tuple[int, int, int]:
    """The team color to paint on an LED panel.

    Prefer the primary color when it has some hue to it; many teams' primary is black or a
    near-black navy, and black is invisible, so fall back to the alternate, then to white-ish
    for teams that are genuinely black-and-silver.
    """
    candidates = [c for c in (primary, alternate) if len(c) == 6]
    for c in candidates:
        r, g, b = (int(c[i : i + 2], 16) / 255 for i in (0, 2, 4))
        _, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s >= 0.3 and v >= 0.12:
            return (round(r * 255), round(g * 255), round(b * 255))
    for c in candidates:
        r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
        if max(r, g, b) >= 128:
            return (r, g, b)
    return (200, 200, 200)
