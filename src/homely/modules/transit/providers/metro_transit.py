"""Metro Transit (Minneapolis-St Paul) NexTrip v2: public, no API key.

Docs: https://svc.metrotransit.org/swagger/index.html
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from homely.modules.transit.providers.base import Choice, Departure, StopBoard, TransitError

BASE_URL = "https://svc.metrotransit.org/nextrip"


def parse_departures(data: dict[str, Any], stop_id: int) -> StopBoard:
    stops = data.get("stops") or []
    name = str(stops[0].get("description", "")) if stops else ""
    deps: list[Departure] = []
    for d in data.get("departures") or []:
        ts = d.get("departure_time")
        if ts is None:
            continue
        deps.append(
            Departure(
                route=str(d.get("route_short_name") or d.get("route_id") or "?"),
                route_id=str(d.get("route_id", "")),
                destination=str(d.get("description") or ""),
                direction=str(d.get("direction_text") or ""),
                time=datetime.fromtimestamp(int(ts), tz=UTC),
                realtime=bool(d.get("actual")),
            )
        )
    deps.sort(key=lambda x: x.time)
    alerts = [str(a["alert_text"]).strip() for a in data.get("alerts") or [] if a.get("alert_text")]
    return StopBoard(stop_id=stop_id, stop_name=name, departures=deps, alerts=alerts)


class MetroTransitProvider:
    name = "metro_transit"

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def _get(self, path: str) -> Any:
        resp = await self._http.get(f"{BASE_URL}/{path}")
        if resp.status_code == 400:
            # NexTrip answers bad stop/route ids with a problem+json body naming the reason.
            try:
                detail = resp.json().get("detail") or "bad request"
            except ValueError:
                detail = "bad request"
            raise TransitError(str(detail))
        resp.raise_for_status()
        return resp.json()

    async def departures(self, stop_id: int) -> StopBoard:
        return parse_departures(await self._get(str(stop_id)), stop_id)

    async def routes(self) -> list[Choice]:
        return [Choice(str(r["route_id"]), str(r["route_label"])) for r in await self._get("routes")]

    async def directions(self, route_id: str) -> list[Choice]:
        data = await self._get(f"directions/{route_id}")
        return [Choice(str(d["direction_id"]), str(d["direction_name"])) for d in data]

    async def stops(self, route_id: str, direction_id: str) -> list[Choice]:
        data = await self._get(f"stops/{route_id}/{direction_id}")
        return [Choice(str(s["place_code"]), str(s["description"])) for s in data]

    async def resolve_stop(self, route_id: str, direction_id: str, place_code: str) -> Choice:
        """A place (station) can have one stop per direction; this finds the one the rider picked."""
        data = await self._get(f"{route_id}/{direction_id}/{place_code}")
        stops = data.get("stops") or []
        if not stops:
            raise TransitError("no stop found for that place")
        return Choice(str(stops[0]["stop_id"]), str(stops[0].get("description", "")))
