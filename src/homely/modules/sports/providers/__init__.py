"""One provider per league. MLB and NHL use the leagues' own public APIs; the rest use ESPN."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from homely.modules.sports.providers.base import Game, SportsProvider, Team, team_color
from homely.modules.sports.providers.espn import EspnProvider
from homely.modules.sports.providers.mlb import MlbProvider
from homely.modules.sports.providers.nhl import NhlProvider


@dataclass(frozen=True)
class League:
    key: str
    name: str
    sport: str  # baseball, football, basketball, hockey, soccer
    espn: str = ""  # ESPN league slug, for leagues served by ESPN


LEAGUES: dict[str, League] = {
    lg.key: lg
    for lg in (
        League("mlb", "MLB", "baseball"),
        League("nfl", "NFL", "football", "nfl"),
        League("nba", "NBA", "basketball", "nba"),
        League("wnba", "WNBA", "basketball", "wnba"),
        League("nhl", "NHL", "hockey"),
        League("mls", "MLS", "soccer", "usa.1"),
        League("epl", "Premier League", "soccer", "eng.1"),
    )
}


def make_provider(league: str, http: httpx.AsyncClient) -> SportsProvider:
    if league == "mlb":
        return MlbProvider(http)
    if league == "nhl":
        return NhlProvider(http)
    lg = LEAGUES[league]
    return EspnProvider(http, lg.key, lg.sport, lg.espn)


__all__ = ["LEAGUES", "Game", "League", "SportsProvider", "Team", "make_provider", "team_color"]
