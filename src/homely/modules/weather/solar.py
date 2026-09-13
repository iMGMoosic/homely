"""Sun times from latitude/longitude (NOAA solar position equations, accurate to ~1 minute).

Used for the sky gradient: astronomical dawn/dusk (sun 18 degrees below the horizon),
sunrise/sunset (-0.833 degrees, includes refraction) and solar noon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo

SUNRISE_DEPRESSION = 0.833
ASTRONOMICAL_DEPRESSION = 18.0


@dataclass(frozen=True)
class SunTimes:
    dawn: datetime | None  # astronomical dawn
    sunrise: datetime | None
    noon: datetime
    sunset: datetime | None
    dusk: datetime | None  # astronomical dusk

    @property
    def polar(self) -> bool:
        return self.sunrise is None or self.sunset is None


def _julian_day(d: date) -> float:
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045 - 0.5


def _solar_params(jd: float) -> tuple[float, float]:
    """(equation of time in minutes, solar declination in degrees) for a Julian day."""
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    mr = math.radians(m)
    c = (
        math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
        + math.sin(3 * mr) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    e0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliq = e0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(obliq)) * math.sin(math.radians(app_long))))
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    y = math.tan(math.radians(obliq) / 2) ** 2
    l0r, mr2 = math.radians(l0), math.radians(m)
    eot = 4 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr2)
        + 4 * e * y * math.sin(mr2) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr2)
    )
    return eot, decl


def _hour_angle(lat: float, decl: float, depression: float) -> float | None:
    """Hour angle (degrees) at which the sun center is `depression` degrees below the horizon."""
    lat_r, decl_r = math.radians(lat), math.radians(decl)
    cos_ha = (math.cos(math.radians(90 + depression)) - math.sin(lat_r) * math.sin(decl_r)) / (
        math.cos(lat_r) * math.cos(decl_r)
    )
    if cos_ha < -1 or cos_ha > 1:
        return None
    return math.degrees(math.acos(cos_ha))


def sun_times(lat: float, lon: float, day: date, tz: tzinfo) -> SunTimes:
    jd = _julian_day(day)
    eot, decl = _solar_params(jd + 0.5)
    noon_minutes_utc = 720 - 4 * lon - eot
    midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
    noon = midnight + timedelta(minutes=noon_minutes_utc)

    def at(depression: float, rising: bool) -> datetime | None:
        ha = _hour_angle(lat, decl, depression)
        if ha is None:
            return None
        minutes = noon_minutes_utc + (-4 * ha if rising else 4 * ha)
        return (midnight + timedelta(minutes=minutes)).astimezone(tz)

    return SunTimes(
        dawn=at(ASTRONOMICAL_DEPRESSION, True),
        sunrise=at(SUNRISE_DEPRESSION, True),
        noon=noon.astimezone(tz),
        sunset=at(SUNRISE_DEPRESSION, False),
        dusk=at(ASTRONOMICAL_DEPRESSION, False),
    )
