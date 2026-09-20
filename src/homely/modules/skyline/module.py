"""Day/night skyline: a procedurally generated city under a sky whose colors follow the sun.
The sun and moon arc across, stars come out after dusk, windows light up in the evening and
go dark toward morning, and cars pass on the street. Uses the weather module's sky palette and
solar calculator so the sky matches your location."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.skyline.settings import SkylineSettings
from homely.modules.weather.colors import sky_gradient
from homely.modules.weather.solar import SunTimes, sun_times
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, lerp, parse_color
from homely.render.layout import layout_fallback
from homely.render.size import Size

SUN: Color = (255, 214, 90)
MOON: Color = (230, 232, 210)
STAR: Color = (255, 255, 240)


@dataclass
class Building:
    x: int
    w: int
    h: int
    color: Color
    back: bool
    windows: list[tuple[int, int]]  # (x, y) top-left of each 1px window
    lit: set[int]  # indexes into windows
    antenna: bool


@dataclass
class Car:
    x: float
    speed: float
    color: Color


class SkylineModule(Module[SkylineSettings]):
    info = ModuleInfo(
        id="skyline",
        name="Skyline",
        description="Idle animation: a city skyline through a day and night that match your sky.",
        tier=Tier.NEED,
        icon="skyline",
        default_duration_s=120,
        default_fps=15,
        min_size=Size(32, 16),
    )
    Settings = SkylineSettings

    def __init__(self, ctx: ModuleContext, settings: SkylineSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self.cars: list[Car] = []
        self._start: datetime | None = None
        self._sun_cache: tuple[object, SunTimes | None] | None = None
        self._reset(ctx.size)

    # ---- city ------------------------------------------------------------------------------

    def _reset(self, size: Size) -> None:
        w, h = size.w, size.h
        self.size = size
        self.street_h = 2 if h >= 32 else 1
        self.horizon = h - self.street_h
        self.buildings: list[Building] = []
        for back in (True, False):
            x = self.rng.randint(-3, 1)
            while x < w:
                bw = self.rng.randint(max(3, w // 16), max(5, w // 6))
                if self.rng.random() * 100 > self.settings.density and not back:
                    x += bw
                    continue
                max_h = h * (0.45 if back else 0.7)
                bh = int(self.rng.uniform(h * 0.15, max_h))
                shade = self.rng.uniform(0.6, 1.0)
                base: Color = (int(40 * shade), int(44 * shade), int(60 * shade)) if not back else (18, 20, 34)
                windows: list[tuple[int, int]] = []
                if not back:
                    for wy in range(self.horizon - bh + 2, self.horizon - 1, 2):
                        for wx in range(x + 1, x + bw - 1, 2):
                            windows.append((wx, wy))
                lit = {i for i in range(len(windows)) if self.rng.random() < 0.15}
                self.buildings.append(
                    Building(
                        x,
                        bw,
                        bh,
                        base,
                        back,
                        windows,
                        lit,
                        antenna=(not back and self.rng.random() < 0.25 and bh > h * 0.4),
                    )
                )
                x += bw + (0 if back else self.rng.randint(0, 1))
        self.stars = [
            (self.rng.randrange(w), self.rng.randrange(max(1, int(h * 0.55))), self.rng.random())
            for _ in range(max(6, w * h // 200))
        ]
        self._window_timer = 0.0
        self._start = None

    # ---- time ---------------------------------------------------------------------------------

    def _now(self, frame: FrameInfo) -> datetime:
        if self.settings.mode == "realtime":
            return frame.now
        if self._start is None:
            self._start = frame.now
        return self._start + timedelta(days=frame.slot_elapsed / self.settings.day_length_s)

    def _sun(self, now: datetime) -> SunTimes | None:
        key = now.date()
        if self._sun_cache is None or self._sun_cache[0] != key:
            latlon = self.ctx.location.latlon
            st = sun_times(latlon[0], latlon[1], key, now.tzinfo or self.ctx.location.tz) if latlon else None
            self._sun_cache = (key, st)
        return self._sun_cache[1]

    @staticmethod
    def _fallback_sun(now: datetime) -> tuple[datetime, datetime]:
        return now.replace(hour=6, minute=30, second=0, microsecond=0), now.replace(
            hour=19, minute=30, second=0, microsecond=0
        )

    def _daylight(self, now: datetime, sun: SunTimes | None) -> float | None:
        """0..1 through the day when the sun is up, else None."""
        if sun is not None and sun.sunrise and sun.sunset:
            rise, set_ = sun.sunrise, sun.sunset
        else:
            rise, set_ = self._fallback_sun(now)
        if rise <= now <= set_:
            return (now - rise).total_seconds() / max(1.0, (set_ - rise).total_seconds())
        return None

    def _night_fraction(self, now: datetime, sun: SunTimes | None) -> float | None:
        """0..1 through the night (sunset -> next sunrise) when the sun is down."""
        if sun is not None and sun.sunrise and sun.sunset:
            rise, set_ = sun.sunrise, sun.sunset
        else:
            rise, set_ = self._fallback_sun(now)
        if now > set_:
            return (now - set_).total_seconds() / max(1.0, (rise + timedelta(days=1) - set_).total_seconds())
        if now < rise:
            return (now - (set_ - timedelta(days=1))).total_seconds() / max(
                1.0, (rise - (set_ - timedelta(days=1))).total_seconds()
            )
        return None

    # ---- animation ---------------------------------------------------------------------------

    def _tick_windows(self, dt: float, darkness: float) -> None:
        """Windows drift toward a target lit fraction: few by day, most at night."""
        self._window_timer += dt
        if self._window_timer < 0.4:
            return
        self._window_timer = 0.0
        target = 0.12 + 0.6 * darkness
        for b in self.buildings:
            if not b.windows:
                continue
            want = int(len(b.windows) * target)
            if len(b.lit) < want and self.rng.random() < 0.7:
                choices = [i for i in range(len(b.windows)) if i not in b.lit]
                if choices:
                    b.lit.add(self.rng.choice(choices))
            elif len(b.lit) > want and self.rng.random() < 0.7:
                b.lit.discard(self.rng.choice(sorted(b.lit)))

    def _tick_cars(self, dt: float, w: int) -> None:
        if not self.settings.traffic:
            self.cars = []
            return
        for car in self.cars:
            car.x += car.speed * dt
        self.cars = [c for c in self.cars if -4 <= c.x <= w + 4]
        if len(self.cars) < 2 and self.rng.random() < dt * 0.4:
            right = self.rng.random() < 0.5
            self.cars.append(
                Car(
                    x=-3.0 if right else w + 3.0,
                    speed=(w / 4) * (1 if right else -1),
                    color=(255, 240, 200) if right else (255, 60, 40),
                )
            )

    def on_enter(self) -> None:
        # Every turn builds a new city and restarts the timelapse day at the current time.
        self._reset(self.ctx.size)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if c.size != self.size:
            self._reset(c.size)
        dt = min(frame.dt, 0.25)
        now = self._now(frame)
        sun = self._sun(now)
        top, bottom = sky_gradient(now, sun) if sun is not None else self._fallback_gradient(now)
        c.sub(0, 0, c.width, self.horizon).fill_gradient_v(top, bottom)
        w, h = c.width, c.height
        day = self._daylight(now, sun)
        night = self._night_fraction(now, sun)
        darkness = 1.0 if night is not None else (0.0 if 0.1 < (day or 0) < 0.9 else 0.5)
        # stars fade in with darkness
        if self.settings.stars and night is not None:
            twinkle_t = frame.monotonic
            for sx, sy, phase in self.stars:
                k = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(twinkle_t * 2 + phase * 6.28))
                if sy < self.horizon - 2:
                    strength = k * min(1.0, night * 6, (1 - night) * 6)
                    c.pixel(sx, sy, lerp(c.get_pixel(sx, sy), STAR, strength))
        # sun or moon arc
        if day is not None:
            ang = math.pi * day
            sx, sy = int(w * 0.08 + (w * 0.84) * day), int(self.horizon * 0.95 - math.sin(ang) * self.horizon * 0.75)
            r = max(1, min(w, h) // 20)
            self._disc(c, sx, sy, r, SUN, glow=True)
        elif night is not None:
            ang = math.pi * night
            mx, my = int(w * 0.92 - (w * 0.84) * night), int(self.horizon * 0.95 - math.sin(ang) * self.horizon * 0.7)
            r = max(1, min(w, h) // 24)
            self._disc(c, mx, my, r, MOON, glow=False)
        # buildings, back layer first
        win = parse_color(self.settings.window_color)
        for b in sorted(self.buildings, key=lambda b: not b.back):
            top_y = self.horizon - b.h
            col = lerp(b.color, (0, 0, 0), 0.35 * darkness) if not b.back else lerp(b.color, bottom, 0.35)
            c.rect(b.x, top_y, b.w, b.h, fill=col)
            if b.antenna:
                c.vline(
                    b.x + b.w // 2, top_y - max(2, b.h // 8), max(2, b.h // 8), dim(col, 1.4) if sum(col) < 300 else col
                )
                if int(frame.monotonic * 2) % 2 == 0:
                    c.pixel(b.x + b.w // 2, top_y - max(2, b.h // 8), (255, 40, 40))
            for i, (wx, wy) in enumerate(b.windows):
                if i in b.lit:
                    c.pixel(wx, wy, win)
                else:
                    c.pixel(wx, wy, dim(col, 0.6))
        self._tick_windows(dt, darkness)
        # street and cars
        c.rect(0, self.horizon, w, self.street_h, fill=(22, 22, 26))
        self._tick_cars(dt, w)
        for car in self.cars:
            c.pixel(int(car.x), self.horizon, car.color)
            if self.street_h > 1:
                c.pixel(int(car.x) - (1 if car.speed > 0 else -1), self.horizon, dim(car.color, 0.5))

    def _fallback_gradient(self, now: datetime) -> tuple[Color, Color]:
        rise, set_ = self._fallback_sun(now)
        fake = SunTimes(
            dawn=rise - timedelta(minutes=80),
            sunrise=rise,
            noon=rise + (set_ - rise) / 2,
            sunset=set_,
            dusk=set_ + timedelta(minutes=80),
        )
        return sky_gradient(now, fake)

    def _disc(self, c: Canvas, cx: int, cy: int, r: int, color: Color, *, glow: bool) -> None:
        for y in range(-r - 1, r + 2):
            for x in range(-r - 1, r + 2):
                d = math.hypot(x, y)
                if d <= r + 0.3:
                    c.pixel(cx + x, cy + y, color)
                elif glow and d <= r + 1.6:
                    px = cx + x
                    py = cy + y
                    if 0 <= px < c.width and 0 <= py < self.horizon:
                        c.pixel(px, py, lerp(c.get_pixel(px, py), color, 0.35))
