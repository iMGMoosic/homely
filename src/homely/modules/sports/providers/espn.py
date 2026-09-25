"""ESPN's unofficial scoreboard API, for the leagues without a public official feed.

It is unauthenticated and undocumented; it has been known to answer 403 for a while from one
host and not the other, so every request falls back to a second host.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from homely.modules.sports.providers.base import Game, State, Team, to_int

HOSTS = ("https://site.api.espn.com", "https://site.web.api.espn.com")
PATH = "/apis/site/v2/sports/{sport}/{league}/scoreboard"


def _team(c: dict[str, Any]) -> Team:
    t = c.get("team") or {}
    abbr = str(t.get("abbreviation", "?")).upper()
    return Team(
        abbr=abbr,
        name=str(t.get("shortDisplayName") or t.get("name") or abbr),
        score=to_int(c.get("score")),
        color=str(t.get("color") or ""),
        alt_color=str(t.get("alternateColor") or ""),
    )


def _status(ev: dict[str, Any], sport: str) -> tuple[State, str]:
    st = ev.get("status") or {}
    kind = st.get("type") or {}
    name = str(kind.get("name", ""))
    state = kind.get("state", "pre")
    if name in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_SUSPENDED", "STATUS_DELAYED") and state != "in":
        return "off", {"STATUS_POSTPONED": "PPD", "STATUS_CANCELED": "CANC"}.get(name, "SUSP")
    if state == "pre":
        return "pre", ""
    period = to_int(st.get("period")) or 0
    if state == "post":
        detail = str(kind.get("shortDetail", "Final")).upper()
        return "final", detail.replace(" ", "") if "/" in detail else "FINAL"
    if name == "STATUS_HALFTIME":
        return "live", "HALF"
    if name == "STATUS_END_PERIOD":
        return "live", f"END {_period(period, sport)}"
    clock = str(st.get("displayClock", ""))
    if sport == "soccer":
        return "live", clock or "LIVE"
    return "live", f"{_period(period, sport)} {clock}".strip()


def _period(n: int, sport: str) -> str:
    if n > 4 and sport in ("football", "basketball"):
        return "OT" if n == 5 else f"{n - 4}OT"
    return f"Q{n}"


def parse_scoreboard(data: dict[str, Any], league: str, sport: str) -> list[Game]:
    out: list[Game] = []
    for ev in data.get("events") or []:
        comps = ev.get("competitions") or [{}]
        sides = {c.get("homeAway"): c for c in comps[0].get("competitors") or []}
        if "home" not in sides or "away" not in sides:
            continue
        state, status = _status(ev, sport)
        raw = str(ev.get("date", ""))
        start = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        out.append(
            Game(
                league=league,
                id=str(ev.get("id")),
                start=start,
                state=state,
                away=_team(sides["away"]),
                home=_team(sides["home"]),
                status=status,
            )
        )
    return out


class EspnProvider:
    def __init__(self, http: httpx.AsyncClient, league: str, sport: str, espn_league: str) -> None:
        self._http = http
        self.league = league
        self.sport = sport
        self.espn_league = espn_league

    async def games(self, day: date) -> list[Game]:
        path = PATH.format(sport=self.sport, league=self.espn_league)
        params = {"dates": day.strftime("%Y%m%d")}
        last: Exception | None = None
        for host in HOSTS:
            try:
                resp = await self._http.get(host + path, params=params)
                resp.raise_for_status()
                return parse_scoreboard(resp.json(), self.league, self.sport)
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
        assert last is not None
        raise last
