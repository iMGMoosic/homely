"""Weather color scales (from Leah's weather prototype): temperature -> color, and the two-tone
sky gradient for a moment of the day."""

from __future__ import annotations

from datetime import datetime

from homely.modules.weather.solar import SunTimes
from homely.render.color import Color, lerp

# One stop every 5 F from -60 to 120 (pale ice blue -> deep blue -> teal -> sand -> red -> maroon).
TEMP_STOPS: tuple[Color, ...] = (
    (228, 240, 255), (220, 233, 250), (211, 226, 247), (203, 219, 244), (192, 212, 237), (183, 205, 233),
    (175, 198, 230), (167, 191, 227), (156, 184, 223), (147, 177, 215), (137, 165, 205), (127, 155, 195),
    (117, 145, 185), (96, 123, 166), (86, 113, 156), (77, 101, 145), (65, 92, 135), (57, 81, 127),
    (47, 71, 117), (38, 67, 111), (37, 79, 119), (39, 91, 128), (39, 103, 138), (40, 117, 147),
    (67, 129, 144), (100, 141, 137), (135, 154, 132), (171, 168, 125), (194, 171, 117), (193, 157, 97),
    (195, 138, 83), (190, 112, 76), (175, 77, 78), (159, 41, 76), (135, 32, 62), (110, 21, 49),
    (86, 12, 37), (61, 2, 22),
)  # fmt: skip
_T0, _STEP = -60.0, 5.0

NIGHT: tuple[Color, Color] = ((19, 24, 98), (9, 12, 49))
SUNRISE: tuple[Color, Color] = ((247, 193, 106), (244, 170, 50))
NOON: tuple[Color, Color] = ((135, 206, 235), (85, 185, 227))


def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def temp_color(temp: float, metric: bool = False) -> Color:
    f = c_to_f(temp) if metric else temp
    if f <= _T0:
        return TEMP_STOPS[0]
    if f >= _T0 + _STEP * (len(TEMP_STOPS) - 1):
        return TEMP_STOPS[-1]
    pos = (f - _T0) / _STEP
    i = int(pos)
    return lerp(TEMP_STOPS[i], TEMP_STOPS[i + 1], pos - i)


def _pair(a: tuple[Color, Color], b: tuple[Color, Color], ratio: float) -> tuple[Color, Color]:
    return lerp(a[0], b[0], ratio), lerp(a[1], b[1], ratio)


def sky_gradient(t: datetime, sun: SunTimes) -> tuple[Color, Color]:
    """(top, bottom) sky colors at time t: night -> sunrise tones -> noon -> sunset tones -> night."""
    if sun.polar or sun.dawn is None or sun.sunrise is None or sun.sunset is None or sun.dusk is None:
        # Polar day/night: pick by whether the sun is up at all.
        return NOON if sun.sunrise is not None else NIGHT

    def ratio(a: datetime, b: datetime) -> float:
        span = (b - a).total_seconds()
        return 0.0 if span <= 0 else min(1.0, max(0.0, (t - a).total_seconds() / span))

    if t < sun.dawn or t > sun.dusk:
        return NIGHT
    if t < sun.sunrise:
        return _pair(NIGHT, SUNRISE, ratio(sun.dawn, sun.sunrise))
    if t < sun.noon:
        return _pair(SUNRISE, NOON, ratio(sun.sunrise, sun.noon))
    if t < sun.sunset:
        return _pair(NOON, SUNRISE, ratio(sun.noon, sun.sunset))
    return _pair(SUNRISE, NIGHT, ratio(sun.sunset, sun.dusk))
