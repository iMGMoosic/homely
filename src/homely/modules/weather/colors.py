"""Color scales for weather: temperature -> color, and the sky color across a day."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise

from homely.render.color import Color, lerp

# Temperature stops in Fahrenheit (metric input is converted first).
_TEMP_STOPS: list[tuple[float, Color]] = [
    (-20, (150, 60, 220)),  # deep purple
    (10, (90, 60, 255)),  # violet-blue
    (32, (40, 110, 255)),  # blue (freezing)
    (45, (0, 180, 255)),  # sky blue
    (58, (0, 210, 160)),  # teal
    (68, (110, 220, 60)),  # green
    (78, (255, 210, 0)),  # yellow
    (88, (255, 130, 0)),  # orange
    (98, (255, 40, 0)),  # red
    (115, (190, 0, 70)),  # crimson
]


def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def temp_color(temp: float, metric: bool = False) -> Color:
    f = c_to_f(temp) if metric else temp
    if f <= _TEMP_STOPS[0][0]:
        return _TEMP_STOPS[0][1]
    for (t0, c0), (t1, c1) in pairwise(_TEMP_STOPS):
        if f <= t1:
            return lerp(c0, c1, (f - t0) / (t1 - t0))
    return _TEMP_STOPS[-1][1]


NIGHT_SKY: Color = (6, 10, 70)
DAWN_SKY: Color = (255, 170, 40)
DAY_SKY: Color = (70, 165, 255)
TWILIGHT = timedelta(minutes=35)  # half-width of the dawn/dusk band


def sky_color(t: datetime, sunrise: datetime | None, sunset: datetime | None) -> Color:
    """Sky color at time t: dark blue -> yellow (sunrise) -> sky blue -> yellow (sunset) -> dark blue."""
    if sunrise is None or sunset is None:
        # No sun data: assume 6:30-19:30
        sunrise = t.replace(hour=6, minute=30, second=0, microsecond=0)
        sunset = t.replace(hour=19, minute=30, second=0, microsecond=0)
    for edge in (sunrise, sunset):
        d = abs((t - edge).total_seconds()) / TWILIGHT.total_seconds()
        if d < 1.0:
            # Blend toward whichever side we are on.
            toward_day = (t > edge) == (edge is sunrise)
            other = DAY_SKY if toward_day else NIGHT_SKY
            return lerp(DAWN_SKY, other, d)
    return DAY_SKY if sunrise < t < sunset else NIGHT_SKY
