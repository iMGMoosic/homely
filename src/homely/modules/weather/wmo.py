"""WMO weather interpretation codes -> icon kind + short label."""

from __future__ import annotations

from homely.render.weather_icons import IconKind

_TABLE: dict[int, tuple[IconKind, str]] = {
    0: ("clear", "Clear"),
    1: ("clear", "Mostly clear"),
    2: ("partly", "Partly cloudy"),
    3: ("cloudy", "Overcast"),
    45: ("fog", "Fog"),
    48: ("fog", "Icy fog"),
    51: ("drizzle", "Light drizzle"),
    53: ("drizzle", "Drizzle"),
    55: ("drizzle", "Heavy drizzle"),
    56: ("sleet", "Freezing drizzle"),
    57: ("sleet", "Freezing drizzle"),
    61: ("rain", "Light rain"),
    63: ("rain", "Rain"),
    65: ("heavy_rain", "Heavy rain"),
    66: ("sleet", "Freezing rain"),
    67: ("sleet", "Freezing rain"),
    71: ("snow", "Light snow"),
    73: ("snow", "Snow"),
    75: ("snow", "Heavy snow"),
    77: ("snow", "Snow grains"),
    80: ("rain", "Showers"),
    81: ("rain", "Showers"),
    82: ("heavy_rain", "Heavy showers"),
    85: ("snow", "Snow showers"),
    86: ("snow", "Snow showers"),
    95: ("thunder", "Thunderstorm"),
    96: ("thunder", "Storm, hail"),
    99: ("thunder", "Storm, hail"),
}


def icon_for(code: int, is_day: bool = True) -> IconKind:
    kind = _TABLE.get(code, ("cloudy", "Unknown"))[0]
    if code == 1 and not is_day:
        return "clear"
    return kind


def label_for(code: int, is_day: bool = True) -> str:
    if code == 0:
        return "Sunny" if is_day else "Clear"
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
        "rain": "Rain",
        "heavy_rain": "Rain",
        "snow": "Snow",
        "sleet": "Sleet",
        "thunder": "Storm",
        "hail": "Hail",
    }[kind]
