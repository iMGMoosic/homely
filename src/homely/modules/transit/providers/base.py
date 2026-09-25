"""Provider-neutral transit model: a stop, its upcoming departures and any service alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class Departure:
    route: str  # what riders call it: "Blue", "2", "A"
    route_id: str
    destination: str
    direction: str  # short direction label, e.g. "SB"
    time: datetime  # timezone-aware
    realtime: bool  # True when the time comes from vehicle tracking, False when it is the timetable

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "route_id": self.route_id,
            "destination": self.destination,
            "direction": self.direction,
            "time": self.time.isoformat(),
            "realtime": self.realtime,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Departure:
        return cls(
            route=d["route"],
            route_id=d.get("route_id", d["route"]),
            destination=d.get("destination", ""),
            direction=d.get("direction", ""),
            time=datetime.fromisoformat(d["time"]),
            realtime=bool(d.get("realtime", False)),
        )


@dataclass(frozen=True)
class StopBoard:
    stop_id: int
    stop_name: str
    departures: list[Departure] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_id": self.stop_id,
            "stop_name": self.stop_name,
            "departures": [d.to_dict() for d in self.departures],
            "alerts": list(self.alerts),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StopBoard:
        return cls(
            stop_id=int(d["stop_id"]),
            stop_name=d.get("stop_name", ""),
            departures=[Departure.from_dict(x) for x in d.get("departures", [])],
            alerts=[str(a) for a in d.get("alerts", [])],
        )


@dataclass(frozen=True)
class Choice:
    """One option in the stop picker (a route, a direction, or a stop on a route)."""

    id: str
    label: str


class TransitError(Exception):
    """The agency rejected the request (unknown stop, route out of service, ...)."""


class TransitProvider(Protocol):
    name: str

    async def departures(self, stop_id: int) -> StopBoard: ...

    # The stop picker walks route -> direction -> stop -> stop id.
    async def routes(self) -> list[Choice]: ...

    async def directions(self, route_id: str) -> list[Choice]: ...

    async def stops(self, route_id: str, direction_id: str) -> list[Choice]: ...

    async def resolve_stop(self, route_id: str, direction_id: str, place_code: str) -> Choice: ...
