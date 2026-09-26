"""Provider-neutral scoreboard model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol

from homely.modules.sports.teams import PALETTES, Palette
from homely.render.color import readable_on

State = Literal["pre", "live", "final", "off"]  # off = postponed, suspended, cancelled


@dataclass(frozen=True)
class Team:
    abbr: str
    name: str  # short name riders of the bus would say: "Twins", "Wild"
    score: int | None
    color: str = ""  # ESPN's primary color, hex without '#'; empty for MLB and NHL (see teams.py)
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


def _hex(value: str) -> tuple[int, int, int] | None:
    if len(value) != 6:
        return None
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return None


def palette_for(league: str, team: Team) -> Palette:
    """The team's palette from the table; for leagues it does not cover, built from ESPN's colors.

    ESPN sends a primary and an alternate color: the primary becomes the band, the alternate the
    bar, and the text is black or white, whichever reads on the band.
    """
    table = PALETTES.get(league, {})
    if team.abbr in table:
        return table[team.abbr]
    home = _hex(team.color) or UNKNOWN.home
    accent = _hex(team.alt_color) or home
    return Palette(home, readable_on(home), accent)


UNKNOWN = Palette((40, 40, 40), (221, 221, 221), (120, 120, 120))
