"""NHL's public web API (api-web.nhle.com); no key."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from homely.modules.sports.providers.base import Game, State, Team, to_int

SCORE_URL = "https://api-web.nhle.com/v1/score/{day}"


def _team(t: dict[str, Any]) -> Team:
    abbr = str(t.get("abbrev", "?")).upper()
    name = t.get("name") or {}
    return Team(
        abbr=abbr,
        name=str(name.get("default", abbr)) if isinstance(name, dict) else str(name),
        score=to_int(t.get("score")),
    )


def _period(pd: dict[str, Any]) -> str:
    kind = pd.get("periodType", "REG")
    n = to_int(pd.get("number")) or 1
    if kind == "SO":
        return "SO"
    if kind == "OT":
        extra = n - (to_int(pd.get("maxRegulationPeriods")) or 3)
        return "OT" if extra <= 1 else f"{extra}OT"
    return f"P{n}"


def _status(g: dict[str, Any]) -> tuple[State, str]:
    state = g.get("gameState", "FUT")
    sched = g.get("gameScheduleState", "OK")
    if sched in ("PPD", "SUSP", "CNCL"):
        return "off", {"PPD": "PPD", "SUSP": "SUSP", "CNCL": "CANC"}[sched]
    if state in ("FUT", "PRE"):
        return "pre", ""
    pd = g.get("periodDescriptor") or {}
    if state in ("OFF", "FINAL"):
        last = (g.get("gameOutcome") or {}).get("lastPeriodType", "REG")
        return "final", "FINAL" if last == "REG" else f"FINAL/{_period(pd) if last == 'OT' else 'SO'}"
    clock = g.get("clock") or {}
    if clock.get("inIntermission"):
        return "live", f"{_period(pd)} INT"
    remaining = str(clock.get("timeRemaining", "")).lstrip("0") or "0:00"
    if remaining.startswith(":"):
        remaining = "0" + remaining
    return "live", f"{_period(pd)} {remaining}"


def parse_score(data: dict[str, Any]) -> list[Game]:
    out: list[Game] = []
    for g in data.get("games") or []:
        state, status = _status(g)
        out.append(
            Game(
                league="nhl",
                id=str(g.get("id")),
                start=datetime.fromisoformat(str(g["startTimeUTC"]).replace("Z", "+00:00")),
                state=state,
                away=_team(g.get("awayTeam") or {}),
                home=_team(g.get("homeTeam") or {}),
                status=status,
            )
        )
    return out


class NhlProvider:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def games(self, day: date) -> list[Game]:
        resp = await self._http.get(SCORE_URL.format(day=day.isoformat()), follow_redirects=True)
        resp.raise_for_status()
        return parse_score(resp.json())
