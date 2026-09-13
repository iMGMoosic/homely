"""Open-Meteo: free, no API key, non-commercial use (data CC BY 4.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from homely.data.location import Units
from homely.modules.weather.providers.base import Current, Daily, Forecast, Hourly

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoProvider:
    name = "open_meteo"
    attribution = "Weather data by Open-Meteo.com"

    def __init__(self, http: httpx.AsyncClient, *, forecast_days: int = 5) -> None:
        self._http = http
        self.forecast_days = forecast_days

    def params(self, lat: float, lon: float, units: Units, timezone: str) -> dict[str, Any]:
        imperial = units == "imperial"
        return {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "is_day",
                    "weather_code",
                    "wind_speed_10m",
                    "precipitation",
                    "relative_humidity_2m",
                ]
            ),
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "sunrise",
                    "sunset",
                ]
            ),
            "timezone": timezone,
            "temperature_unit": "fahrenheit" if imperial else "celsius",
            "wind_speed_unit": "mph" if imperial else "kmh",
            "precipitation_unit": "inch" if imperial else "mm",
            "forecast_days": str(self.forecast_days),
        }

    async def fetch(self, lat: float, lon: float, units: Units, timezone: str) -> Forecast:
        resp = await self._http.get(FORECAST_URL, params=self.params(lat, lon, units, timezone))
        resp.raise_for_status()
        return parse_forecast(resp.json(), units, self.attribution)


def parse_forecast(data: dict[str, Any], units: Units, attribution: str = "") -> Forecast:
    tz = ZoneInfo(data.get("timezone") or "UTC")

    def local(s: str | None) -> datetime | None:
        return datetime.fromisoformat(s).replace(tzinfo=tz) if s else None

    cur = data["current"]
    current = Current(
        time=local(cur["time"]),  # type: ignore[arg-type]
        temp=float(cur["temperature_2m"]),
        feels_like=float(cur.get("apparent_temperature", cur["temperature_2m"])),
        code=int(cur["weather_code"]),
        is_day=bool(cur.get("is_day", 1)),
        wind_speed=float(cur.get("wind_speed_10m", 0.0)),
        humidity=int(cur["relative_humidity_2m"]) if cur.get("relative_humidity_2m") is not None else None,
        precipitation=float(cur.get("precipitation") or 0.0),
    )
    hourly: list[Hourly] = []
    h = data.get("hourly", {})
    probs = h.get("precipitation_probability") or []
    for i, t in enumerate(h.get("time", [])):
        temp = h["temperature_2m"][i]
        if temp is None:
            continue
        hourly.append(
            Hourly(
                time=local(t),  # type: ignore[arg-type]
                temp=float(temp),
                code=int(h["weather_code"][i] or 0),
                precip_prob=int(probs[i]) if i < len(probs) and probs[i] is not None else None,
            )
        )
    daily: list[Daily] = []
    d = data.get("daily", {})
    dprobs = d.get("precipitation_probability_max") or []
    for i, t in enumerate(d.get("time", [])):
        if d["temperature_2m_max"][i] is None:
            continue
        daily.append(
            Daily(
                date=local(t),  # type: ignore[arg-type]
                code=int(d["weather_code"][i] or 0),
                tmax=float(d["temperature_2m_max"][i]),
                tmin=float(d["temperature_2m_min"][i]),
                precip_prob=int(dprobs[i]) if i < len(dprobs) and dprobs[i] is not None else None,
                sunrise=local(d["sunrise"][i]) if d.get("sunrise") else None,
                sunset=local(d["sunset"][i]) if d.get("sunset") else None,
            )
        )
    lat = data.get("latitude")
    lon = data.get("longitude")
    return Forecast(
        current=current,
        hourly=hourly,
        daily=daily,
        units=units,
        attribution=attribution,
        latitude=float(lat) if lat is not None else None,
        longitude=float(lon) if lon is not None else None,
    )
