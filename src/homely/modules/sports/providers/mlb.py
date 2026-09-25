"""MLB Stats API (statsapi.mlb.com): free for personal, non-commercial use; no key."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from homely.modules.sports.providers.base import Game, State, Team, to_int
from homely.modules.sports.teams import MLB

SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

_OFF_STATES = ("postponed", "suspended", "cancelled", "canceled")


def _state(status: dict[str, Any]) -> tuple[State, str]:
    detailed = str(status.get("detailedState", ""))
    low = detailed.lower()
    if any(s in low for s in _OFF_STATES):
        return "off", "PPD" if "postponed" in low else "SUSP" if "suspended" in low else "CANC"
    abstract = status.get("abstractGameState")
    if abstract == "Final":
        return "final", "FINAL"
    if abstract == "Live":
        if "delay" in low:
            return "live", "DELAY"
        return "live", ""
    return "pre", ""


def _team(side: dict[str, Any]) -> Team:
    t = side.get("team", {})
    abbr = str(t.get("abbreviation") or t.get("teamCode", "?")).upper()
    primary, alt = MLB.get(abbr, ("", ""))
    return Team(
        abbr=abbr,
        name=str(t.get("teamName") or t.get("clubName") or abbr),
        score=to_int(side.get("score")),
        color=primary,
        alt_color=alt,
    )


def parse_schedule(data: dict[str, Any]) -> list[Game]:
    out: list[Game] = []
    for day in data.get("dates") or []:
        for g in day.get("games") or []:
            state, status = _state(g.get("status", {}))
            ls = g.get("linescore") or {}
            inning = to_int(ls.get("currentInning")) if state != "pre" else None
            if state == "final" and inning and inning != to_int(ls.get("scheduledInnings") or 9):
                status = f"F/{inning}"
            live = state == "live"
            offense = ls.get("offense") or {}
            half = str(ls.get("inningState", ""))
            out.append(
                Game(
                    league="mlb",
                    id=str(g.get("gamePk")),
                    start=datetime.fromisoformat(str(g["gameDate"]).replace("Z", "+00:00")),
                    state=state,
                    away=_team(g["teams"]["away"]),
                    home=_team(g["teams"]["home"]),
                    status=status,
                    inning=inning if live else None,
                    # "Middle" and "End" are the breaks between halves; show the half coming up.
                    top=(half in ("Top", "Middle")) if live else None,
                    outs=to_int(ls.get("outs")) if live and half in ("Top", "Bottom") else None,
                    bases=(("first" in offense), ("second" in offense), ("third" in offense))
                    if live and half in ("Top", "Bottom")
                    else None,
                )
            )
    return out


class MlbProvider:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def games(self, day: date) -> list[Game]:
        resp = await self._http.get(
            SCHEDULE_URL, params={"sportId": "1", "date": day.isoformat(), "hydrate": "linescore,team"}
        )
        resp.raise_for_status()
        return parse_schedule(resp.json())
