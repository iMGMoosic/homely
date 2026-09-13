"""Provider-neutral forecast model. Temperatures are in the requested units already."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol

import httpx

from homely.data.location import Units


@dataclass(frozen=True)
class Current:
    time: datetime
    temp: float
    feels_like: float
    code: int  # WMO weather code
    is_day: bool
    wind_speed: float
    humidity: int | None = None
    precipitation: float = 0.0


@dataclass(frozen=True)
class Hourly:
    time: datetime
    temp: float
    code: int
    precip_prob: int | None


@dataclass(frozen=True)
class Daily:
    date: datetime  # midnight local
    code: int
    tmax: float
    tmin: float
    precip_prob: int | None
    sunrise: datetime | None
    sunset: datetime | None


@dataclass(frozen=True)
class Forecast:
    current: Current
    hourly: list[Hourly] = field(default_factory=list)
    daily: list[Daily] = field(default_factory=list)
    units: Units = "imperial"
    attribution: str = ""
    latitude: float | None = None
    longitude: float | None = None

    def today(self) -> Daily | None:
        return self.daily[0] if self.daily else None

    def to_dict(self) -> dict[str, Any]:
        encoded: dict[str, Any] = _encode(asdict(self))
        return encoded

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Forecast:
        cur = data["current"]
        return cls(
            current=Current(**{**cur, "time": _dt(cur["time"])}),
            hourly=[Hourly(**{**h, "time": _dt(h["time"])}) for h in data.get("hourly", [])],
            daily=[
                Daily(**{**d, "date": _dt(d["date"]), "sunrise": _dt(d["sunrise"]), "sunset": _dt(d["sunset"])})
                for d in data.get("daily", [])
            ],
            units=data.get("units", "imperial"),
            attribution=data.get("attribution", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )


def _encode(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_encode(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class WeatherProvider(Protocol):
    name: str
    attribution: str

    def __init__(self, http: httpx.AsyncClient, *, forecast_days: int = 5) -> None: ...

    async def fetch(self, lat: float, lon: float, units: Units, timezone: str) -> Forecast: ...
