"""WMO weather interpretation codes -> icon kind + short label."""

from __future__ import annotations

from homely.render.weather_icons import IconKind

_TABLE: dict[int, tuple[IconKind, str]] = {
    0: ("clear", "Sunny"),
    1: ("clear", "Mostly Sunny"),
    2: ("partly", "Partly Cloudy"),
    3: ("cloudy", "Cloudy"),
    45: ("fog", "Foggy"),
    48: ("fog", "Foggy"),
    51: ("drizzle", "Drizzle"),
    53: ("drizzle", "Drizzle"),
    55: ("drizzle", "Drizzle"),
    56: ("sleet", "Freezing Drizzle"),
    57: ("sleet", "Freezing Drizzle"),
    61: ("rain", "Rainy"),
    63: ("rain", "Rainy"),
    65: ("heavy_rain", "Rainy"),
    66: ("sleet", "Freezing Rain"),
    67: ("sleet", "Freezing Rain"),
    71: ("snow", "Snowy"),
    73: ("snow", "Snowy"),
    75: ("snow", "Snowy"),
    77: ("snow", "Snowy"),
    80: ("rain", "Rainy"),
    81: ("rain", "Rainy"),
    82: ("heavy_rain", "Rainy"),
    85: ("snow", "Snowy"),
    86: ("snow", "Snowy"),
    95: ("thunder", "Thunderstorms"),
    96: ("thunder", "Thunderstorms"),
    99: ("thunder", "Thunderstorms"),
}


def icon_for(code: int, is_day: bool = True) -> IconKind:
    kind = _TABLE.get(code, ("cloudy", "Unknown"))[0]
    if code == 1 and not is_day:
        return "clear"
    return kind


def label_for(code: int, is_day: bool = True) -> str:
    if code == 0:
        return "Sunny" if is_day else "Clear"
    if code == 1:
        return "Mostly Sunny" if is_day else "Mostly Clear"
    return _TABLE.get(code, ("cloudy", "Unknown"))[1]


def short_label_for(code: int, is_day: bool = True) -> str:
    """<= 7 chars for narrow panels."""
    kind = icon_for(code, is_day)
    return {
        "clear": "Sunny" if is_day else "Clear",
        "partly": "Partly",
        "cloudy": "Cloudy",
        "fog": "Fog",
        "drizzle": "Drizzle",
        "rain": "Rainy",
        "heavy_rain": "Rainy",
        "snow": "Snowy",
        "sleet": "Sleet",
        "thunder": "Storms",
        "hail": "Hail",
    }[kind]
