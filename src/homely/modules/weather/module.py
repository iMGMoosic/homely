"""Weather, after Leah's prototype: the screen splits in two. One half is a gradient from
today's high (top) to low (bottom) in temperature colors with the current temperature and
H:/L: on it; the other half takes the color of the sky right now (night, dawn, day, dusk,
from real sun times) with the condition icon and its name.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.data.slot import DataSlot
from homely.modules.weather.colors import NIGHT, sky_gradient, temp_color
from homely.modules.weather.providers import PROVIDERS, Daily, Forecast, WeatherProvider
from homely.modules.weather.settings import WeatherSettings
from homely.modules.weather.solar import SunTimes, sun_times
from homely.modules.weather.wmo import icon_for, label_for, short_label_for
from homely.render.canvas import Canvas
from homely.render.color import AMBER, BLACK, WHITE, Color, dim, lerp, parse_color
from homely.render.fonts import get_font, get_theme
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.text import fit_text, wrap_text
from homely.render.weather_icons import draw_weather_icon

STALE_AFTER = timedelta(hours=3)
CACHE_KEY = "forecast"
HI_COLOR: Color = (255, 150, 90)
LO_COLOR: Color = (120, 190, 255)
BAR_COLOR: Color = (60, 150, 255)


def deg(t: float) -> str:
    return f"{round(t)}°"


class WeatherModule(Module[WeatherSettings]):
    info = ModuleInfo(
        id="weather",
        name="Weather",
        description="Current conditions on a temperature gradient beside a sky-colored panel with the icon.",
        tier=Tier.NEED,
        icon="weather",
        default_duration_s=20,
        default_fps=1,
        min_size=Size(32, 32),
    )
    Settings = WeatherSettings

    def __init__(self, ctx: ModuleContext, settings: WeatherSettings) -> None:
        super().__init__(ctx, settings)
        self.forecast: DataSlot[Forecast] = DataSlot()
        self._provider: WeatherProvider | None = None
        self._warned_no_location = False

    # ---- data ----------------------------------------------------------------------

    async def setup(self) -> None:
        self._provider = PROVIDERS[self.settings.provider](self.ctx.http, forecast_days=self.settings.forecast_days + 1)
        cached = self.ctx.cache.get(CACHE_KEY, max_age_s=6 * 3600)
        if cached:
            try:
                self.forecast.set(Forecast.from_dict(cached["forecast"]), datetime.fromisoformat(cached["at"]))
            except (KeyError, ValueError, TypeError) as exc:
                self.ctx.log.debug("ignoring bad weather cache: %s", exc)
        self.ctx.poll("forecast", timedelta(minutes=self.settings.refresh_minutes), self._fetch)

    async def on_settings_changed(self, settings: WeatherSettings) -> None:
        refetch = (settings.provider, settings.forecast_days) != (self.settings.provider, self.settings.forecast_days)
        self.settings = settings
        if refetch and self._provider is not None:
            self._provider = PROVIDERS[settings.provider](self.ctx.http, forecast_days=settings.forecast_days + 1)
            for p in self.ctx.pollers:
                p.trigger()
        self.ctx.invalidate()

    async def _fetch(self) -> None:
        latlon = self.ctx.location.latlon
        if latlon is None:
            if not self._warned_no_location:
                self.ctx.log.warning("weather: set a location (latitude/longitude) in Display settings")
                self._warned_no_location = True
            return
        assert self._provider is not None
        tz = self.ctx.location.config.timezone or "auto"
        fc = await self._provider.fetch(latlon[0], latlon[1], self.ctx.location.units, tz)
        now = self.ctx.now()
        self.forecast.set(fc, now)
        self.ctx.cache.set(CACHE_KEY, {"forecast": fc.to_dict(), "at": now.isoformat()})
        self.ctx.invalidate()

    def should_display(self) -> bool:
        return self.forecast.has_value

    # ---- helpers -----------------------------------------------------------------------

    def _page(self, frame: FrameInfo) -> str:
        v = self.settings.view
        if v != "both":
            return v
        return "current" if frame.progress < 0.5 else "forecast"

    def _now(self, fc: Forecast, frame: FrameInfo) -> datetime:
        tz = fc.current.time.tzinfo
        return frame.now.astimezone(tz) if tz is not None else frame.now

    def _sun(self, fc: Forecast, now: datetime) -> SunTimes | None:
        lat, lon = fc.latitude, fc.longitude
        if lat is None or lon is None:
            latlon = self.ctx.location.latlon
            if latlon is None:
                return None
            lat, lon = latlon
        return sun_times(lat, lon, now.date(), now.tzinfo or self.ctx.location.tz)

    def _temp_gradient(self, area: Canvas, fc: Forecast) -> None:
        today = fc.today()
        k = self.settings.background_brightness / 100
        if not self.settings.temperature_gradient or today is None:
            area.clear()
            return
        metric = fc.units == "metric"
        area.fill_gradient_v(dim(temp_color(today.tmax, metric), k), dim(temp_color(today.tmin, metric), k))

    def _sky(self, area: Canvas, fc: Forecast, now: datetime) -> None:
        k = self.settings.background_brightness / 100
        if not self.settings.sky_half:
            area.clear()
            return
        sun = self._sun(fc, now)
        top, bottom = sky_gradient(now, sun) if sun is not None else NIGHT
        area.fill_gradient_v(dim(top, k), dim(bottom, k))

    def _stale_dot(self, c: Canvas, frame: FrameInfo) -> None:
        if self.forecast.is_stale(frame.now, STALE_AFTER):
            c.pixel(0, c.height - 1, dim(AMBER, 0.5))

    def _upcoming_days(self, fc: Forecast, now: datetime) -> list[Daily]:
        days = [d for d in fc.daily if d.date.date() > now.date()]
        return days[: self.settings.forecast_days]

    def _text_color(self) -> Color:
        return parse_color(self.settings.text_color)

    # ---- current conditions ------------------------------------------------------------

    def _temp_side(self, area: Canvas, fc: Forecast) -> None:
        """Temperature gradient with the big current temperature and H:/L: at the bottom."""
        self._temp_gradient(area, fc)
        cur = fc.current
        w, h = area.width, area.height
        metric = fc.units == "metric"
        today = fc.today()
        small = get_font("5x8") if w >= 40 else get_font("4x6")
        hi, lo = (f"H:{deg(today.tmax)}", f"L:{deg(today.tmin)}") if today else ("", "")
        if hi and small.measure(hi) > w - 2:
            small = get_font("4x6")
        if hi and small.measure(hi) > w - 2 and today:
            hi, lo = f"H{round(today.tmax)}", f"L{round(today.tmin)}"
        hilo_h = 2 * small.line_height + 2 if hi else 0
        names = ["10x20", "9x18", "9x15", "7x13B", "6x10", "5x8", "4x6"]
        if get_theme() == "segment":
            names = ["seg:17x33:3", "seg:13x25:2", *names]
        big = [get_font(n) for n in names]
        fits = [f for f in big if f.line_height + 2 + hilo_h <= h and f.measure(deg(cur.temp)) <= w - 2]
        font = fits[0] if fits else big[-1]
        temp = deg(cur.temp) if font.measure(deg(cur.temp)) <= w - 2 else f"{round(cur.temp)}"
        color = temp_color(cur.temp, metric)
        outline = WHITE if self.settings.outline_temperature else None
        area.text(w // 2, 2, temp, font, color, halign="center", outline=outline)
        y = 2 + font.line_height + 1
        if self.settings.show_feels_like and round(cur.feels_like) != round(cur.temp) and h - y >= hilo_h + 8:
            area.text_centered(y, f"FL {deg(cur.feels_like)}", get_font("4x6"), dim(WHITE, 0.8))
        if hi:
            step = small.line_height
            base = h - 2 - 2 * step
            if base >= y:
                area.text(w // 2, base, hi, small, WHITE, halign="center")
                area.text(w // 2, base + step, lo, small, WHITE, halign="center")

    def _sky_side(self, area: Canvas, fc: Forecast, now: datetime) -> None:
        """Sky-colored half with the condition icon and its name."""
        self._sky(area, fc, now)
        cur = fc.current
        w, h = area.width, area.height
        kind = icon_for(cur.code, cur.is_day)
        label_fonts = [get_font("5x8"), get_font("4x6")] if w >= 40 else [get_font("4x6")]
        label = label_for(cur.code, cur.is_day) if w >= 40 else short_label_for(cur.code, cur.is_day)
        lines: list[str] = []
        label_font = label_fonts[-1]
        if self.settings.show_condition:
            for f in label_fonts:
                candidate = wrap_text(label, f, w)
                if len(candidate) <= 2 and all(f.measure(ln) <= w for ln in candidate):
                    label_font, lines = f, candidate
                    break
            else:
                label_font = label_fonts[-1]
                lines = wrap_text(label, label_font, w, max_lines=2)
        text_h = len(lines) * label_font.line_height
        icon = _snap(min(w - 4, h - text_h - 4), (8, 12, 16, 24, 32, 48, 64))
        block = icon + (2 + text_h if lines else 0)
        y = max(0, (h - block) // 2)
        draw_weather_icon(area, (w - icon) // 2, y, icon, kind, is_day=cur.is_day)
        ty = y + icon + 2
        for line in lines:
            area.text(w // 2, ty, line, label_font, WHITE, halign="center", outline=BLACK)
            ty += label_font.line_height
        if self.settings.show_place and self.ctx.location.config.name and h - ty >= 8:
            f, place = fit_text(self.ctx.location.config.name, [get_font("4x6")], w - 2)
            area.text(w // 2, h - f.line_height - 1, place, f, dim(WHITE, 0.8), halign="center", outline=BLACK)

    def _compact(self, c: Canvas, fc: Forecast, now: datetime) -> None:
        """32x32-class panels: no split, temperature gradient behind icon + temp + H/L."""
        self._temp_gradient(c, fc)
        cur = fc.current
        w, h = c.width, c.height
        icon = 12 if h >= 32 else 8
        draw_weather_icon(c, 1, 1, icon, icon_for(cur.code, cur.is_day), is_day=cur.is_day)
        font, temp = fit_text(deg(cur.temp), [get_font("5x8"), get_font("4x6")], w - icon - 3)
        outline = WHITE if self.settings.outline_temperature else None
        area_w = w - icon - 2
        c.text(
            icon + 2 + (area_w - font.measure(temp)) // 2,
            1 + (icon - font.line_height) // 2,
            temp,
            font,
            temp_color(cur.temp, fc.units == "metric"),
            outline=outline,
        )
        small = get_font("4x6")
        today = fc.today()
        y = icon + 3
        if today is not None and h - y >= small.line_height:
            hi, lo = f"H{round(today.tmax)}", f"L{round(today.tmin)}"
            total = small.measure(hi) + 3 + small.measure(lo)
            x = (w - total) // 2
            c.text(x, y, hi, small, WHITE)
            c.text(x + small.measure(hi) + 3, y, lo, small, WHITE)
            y += small.line_height + 1
        if self.settings.show_condition and h - y >= small.line_height:
            f, label = fit_text(short_label_for(cur.code, cur.is_day), [small], w)
            c.text(w // 2, y, label, f, WHITE, halign="center", outline=BLACK)

    def _current(self, c: Canvas, fc: Forecast, now: datetime) -> None:
        w, h = c.width, c.height
        if w < 48 and h < 48:
            self._compact(c, fc, now)
            return
        if w >= h:
            half = w // 2
            self._temp_side(c.sub(0, 0, half, h), fc)
            self._sky_side(c.sub(half + 1, 0, w - half - 1, h), fc, now)
            c.vline(half, 0, h, BLACK)
        else:
            half = h // 2
            self._temp_side(c.sub(0, 0, w, half), fc)
            self._sky_side(c.sub(0, half + 1, w, h - half - 1), fc, now)
            c.hline(0, half, w, BLACK)

    # ---- forecast page -------------------------------------------------------------------

    def _draw_precip_bars(self, c: Canvas, fc: Forecast, now: datetime, y: int, h: int) -> None:
        hours = [hr for hr in fc.hourly if hr.time >= now.replace(minute=0, second=0, microsecond=0)][:12]
        if not hours:
            return
        n = len(hours)
        bar_w = max(1, c.width // n)
        gap = 1 if bar_w > 2 else 0
        base = y + h - 1
        c.hline(0, base, bar_w * n, dim(self._text_color(), 0.4))
        for i, hr in enumerate(hours):
            prob = hr.precip_prob or 0
            bh = round(prob / 100 * (h - 1))
            if bh > 0:
                col = lerp(dim(BAR_COLOR, 0.5), BAR_COLOR, prob / 100)
                c.rect(i * bar_w, base - bh, bar_w - gap, bh, fill=col)

    def _forecast_page(self, area: Canvas, fc: Forecast, now: datetime) -> None:
        self._temp_gradient(area, fc)
        text = self._text_color()
        days = self._upcoming_days(fc, now)
        if not days:
            area.text_centered(area.height // 2 - 3, "NO FORECAST", get_font("4x6"), text)
            return
        icon = 16 if area.height >= 40 else 8
        ncols = min(len(days), area.width // 12)
        if area.height >= area.width * 1.25 or ncols < 2:
            self._forecast_rows(area, fc, days)
            return
        days = days[:ncols]
        col_w = area.width // ncols
        label_font = get_font("4x6") if col_w >= 16 else get_font("tom-thumb")
        num_font = label_font
        icon = min(icon, col_w - 2)
        for i, d in enumerate(days):
            col = area.sub(i * col_w, 0, col_w, area.height)
            col.text_centered(1, d.date.strftime("%a"), label_font, text)
            draw_weather_icon(
                col, (col_w - icon) // 2, 1 + label_font.line_height + 1, icon, icon_for(d.code), is_day=True
            )
            y = 1 + label_font.line_height + 1 + icon + 2
            col.text_centered(y, deg(d.tmax), num_font, HI_COLOR)
            col.text_centered(y + num_font.line_height + 1, deg(d.tmin), num_font, LO_COLOR)
        used = 1 + label_font.line_height + 1 + icon + 2 + 2 * (num_font.line_height + 1)
        if self.settings.show_precip_bars and area.height - used >= 10:
            bar_h = min(14, area.height - used - 2)
            self._draw_precip_bars(area, fc, now, area.height - bar_h, bar_h)

    def _forecast_rows(self, area: Canvas, fc: Forecast, days: list[Daily]) -> None:
        text = self._text_color()
        n = max(1, min(len(days), area.height // 16))
        row_h = min(28, area.height // n)
        icon = _snap(min(row_h - 2, area.width // 2), (8, 12, 16, 24))
        small = get_font("4x6")
        for i, d in enumerate(days[:n]):
            row = area.sub(0, i * row_h, area.width, row_h)
            draw_weather_icon(row, 1, (row_h - icon) // 2, icon, icon_for(d.code), is_day=True)
            x = icon + 3
            top = max(0, (row_h - 3 * small.line_height) // 2)
            row.text(x, top, d.date.strftime("%a"), small, text)
            row.text(x, top + small.line_height, f"H{round(d.tmax)}", small, HI_COLOR)
            row.text(x, top + 2 * small.line_height, f"L{round(d.tmin)}", small, LO_COLOR)

    # ---- entry point -------------------------------------------------------------------------

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        fc = self.forecast.value
        if fc is None:
            return
        now = self._now(fc, frame)
        if self._page(frame) == "forecast":
            self._forecast_page(c, fc, now)
        else:
            self._current(c, fc, now)
        self._stale_dot(c, frame)


def _snap(value: int, steps: tuple[int, ...]) -> int:
    best = steps[0]
    for s in steps:
        if s <= value:
            best = s
    return best
