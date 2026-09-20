"""Weather: current conditions and a daily forecast, Wii-Forecast-Channel flavored.

Background is a vertical gradient from today's high (top) to low (bottom), colored by
temperature; a strip on the right edge shows the sky color across the day with a marker at now.
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
from homely.render.color import AMBER, Color, dim, lerp, parse_color
from homely.render.fonts import get_font
from homely.render.layout import layout, layout_fallback
from homely.render.size import Size
from homely.render.text import fit_text
from homely.render.weather_icons import draw_weather_icon

STALE_AFTER = timedelta(hours=3)
CACHE_KEY = "forecast"
HI_COLOR: Color = (255, 150, 90)
LO_COLOR: Color = (120, 190, 255)
BAR_COLOR: Color = (60, 150, 255)
STRIP_W = 2


def deg(t: float) -> str:
    return f"{round(t)}°"


class WeatherModule(Module[WeatherSettings]):
    info = ModuleInfo(
        id="weather",
        name="Weather",
        description="Current conditions and forecast with friendly icons and a temperature gradient.",
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
        # With no data we still take a turn when something is wrong, so the panel explains itself
        # instead of going blank (no location set, or every fetch so far has failed).
        return self.forecast.has_value or self._status_message() is not None

    def _status_message(self) -> tuple[str, str] | None:
        """(headline, detail) to show when there is no forecast to draw, else None."""
        if self.forecast.has_value:
            return None
        if self.ctx.location.latlon is None:
            return ("No location", "set it in Display settings")
        if self.forecast.error is not None:
            return ("No weather", "check the network")
        return None  # still loading on first start: skip the turn rather than flash a placeholder

    def _draw_status(self, c: Canvas) -> None:
        msg = self._status_message()
        if msg is None:
            return
        head, detail = msg
        text = self._text_color()
        c.clear((18, 20, 30))
        fonts = [get_font(n) for n in ("6x10", "5x8", "4x6", "tom-thumb")]
        hf, htext = fit_text(head, fonts, c.width - 2)
        df, dtext = fit_text(detail, [get_font("4x6"), get_font("tom-thumb")], c.width - 2)
        fits_detail = c.height >= hf.line_height + df.line_height + 3
        top = (c.height - (hf.line_height + (df.line_height + 2 if fits_detail else 0))) // 2
        c.text_centered(top, htext, hf, text)
        if fits_detail:
            c.text_centered(top + hf.line_height + 2, dtext, df, dim(text, 0.7))

    # ---- shared drawing --------------------------------------------------------------

    def _page(self, frame: FrameInfo) -> str:
        v = self.settings.view
        if v != "both":
            return v
        return "current" if frame.progress < 0.5 else "forecast"

    def _content_width(self, c: Canvas) -> int:
        return c.width - (STRIP_W + 2) if self._strip_fits(c) else c.width

    def _strip_fits(self, c: Canvas) -> bool:
        return self.settings.sky_strip and c.width >= 48

    def _background(self, c: Canvas, fc: Forecast) -> None:
        today = fc.today()
        if not self.settings.temperature_gradient or today is None:
            c.clear()
            return
        metric = fc.units == "metric"
        k = self.settings.background_brightness / 100
        c.fill_gradient_v(dim(temp_color(today.tmax, metric), k), dim(temp_color(today.tmin, metric), k))

    def _sun(self, fc: Forecast, now: datetime) -> SunTimes | None:
        lat, lon = fc.latitude, fc.longitude
        if lat is None or lon is None:
            latlon = self.ctx.location.latlon
            if latlon is None:
                return None
            lat, lon = latlon
        return sun_times(lat, lon, now.date(), now.tzinfo or self.ctx.location.tz)

    def _sky_strip(self, c: Canvas, fc: Forecast, now: datetime) -> None:
        """Right-edge strip: the day from midnight (top) to midnight (bottom) in sky colors.

        Each row is the two-tone sky of that moment (left pixel = upper tone, right pixel =
        lower tone): navy at night, warm orange through dawn and dusk, light blue at midday,
        using real sun times. A white marker sits at the current time.
        """
        if not self._strip_fits(c):
            return
        sun = self._sun(fc, now)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        x = c.width - STRIP_W
        for row in range(c.height):
            t = start + timedelta(days=row / c.height)
            top, bottom = sky_gradient(t, sun) if sun is not None else NIGHT
            c.pixel(x, row, top)
            c.pixel(x + 1, row, bottom)
        marker_row = min(c.height - 1, int((now - start).total_seconds() / 86400 * c.height))
        c.hline(x - 2, marker_row, STRIP_W + 2, (255, 255, 255))
        if marker_row > 0:
            c.pixel(x - 2, marker_row - 1, (255, 255, 255))
        if marker_row < c.height - 1:
            c.pixel(x - 2, marker_row + 1, (255, 255, 255))

    def _stale_dot(self, c: Canvas, frame: FrameInfo) -> None:
        if self.forecast.is_stale(frame.now, STALE_AFTER):
            c.pixel(0, c.height - 1, dim(AMBER, 0.5))

    def _frame(self, c: Canvas, frame: FrameInfo) -> tuple[Forecast, Canvas, datetime] | None:
        fc = self.forecast.value
        if fc is None:
            return None
        now = frame.now.astimezone(fc.current.time.tzinfo) if fc.current.time.tzinfo else frame.now
        self._background(c, fc)
        self._sky_strip(c, fc, now)
        self._stale_dot(c, frame)
        return fc, c.sub(0, 0, self._content_width(c), c.height), now

    def _upcoming_days(self, fc: Forecast, now: datetime) -> list[Daily]:
        days = [d for d in fc.daily if d.date.date() > now.date()]
        return days[: self.settings.forecast_days]

    def _text_color(self) -> Color:
        return parse_color(self.settings.text_color)

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

    # ---- 64x64 -------------------------------------------------------------------------

    @layout(64, 64)
    def render_64(self, c: Canvas, frame: FrameInfo) -> None:
        got = self._frame(c, frame)
        if got is None:
            self._draw_status(c)
            return
        fc, area, now = got
        if self._page(frame) == "forecast":
            self._forecast_page(area, fc, now, icon=16)
            return
        cur = fc.current
        text = self._text_color()
        draw_weather_icon(area, 2, 2, 24, icon_for(cur.code, cur.is_day), is_day=cur.is_day)
        font, temp = fit_text(deg(cur.temp), [get_font(n) for n in ("10x20", "9x15", "7x13B")], area.width - 29)
        tx = 28 + (area.width - 28 - font.measure(temp)) // 2
        area.text(tx, 4 + (20 - font.line_height) // 2, temp, font, text)
        y = 29
        if self.settings.show_feels_like and round(cur.feels_like) != round(cur.temp):
            area.text_centered(y, f"feels {deg(cur.feels_like)}", get_font("4x6"), dim(text, 0.7))
            y += 8
        if self.settings.show_condition:
            f, label = fit_text(
                label_for(cur.code, cur.is_day), [get_font("6x10"), get_font("5x8"), get_font("4x6")], area.width
            )
            area.text_centered(y, label, f, text)
            y += f.line_height + 1
        today = fc.today()
        if today is not None:
            f58 = get_font("5x8")
            hi, lo = f"H{deg(today.tmax)}", f"L{deg(today.tmin)}"
            total = f58.measure(hi) + 6 + f58.measure(lo)
            x = (area.width - total) // 2
            area.text(x, y, hi, f58, HI_COLOR)
            area.text(x + f58.measure(hi) + 6, y, lo, f58, LO_COLOR)
            y += 10
        if self.settings.show_place and self.ctx.location.config.name:
            f, place = fit_text(self.ctx.location.config.name, [get_font("4x6"), get_font("tom-thumb")], area.width)
            area.text_centered(max(y, area.height - 7), place, f, dim(text, 0.7))

    def _forecast_page(self, area: Canvas, fc: Forecast, now: datetime, *, icon: int) -> None:
        text = self._text_color()
        days = self._upcoming_days(fc, now)
        if not days:
            area.text_centered(area.height // 2 - 3, "no forecast", get_font("4x6"), text)
            return
        ncols = min(len(days), area.width // 12)
        if area.height >= area.width * 1.25 or ncols < 2:
            self._forecast_rows(area, fc, now, days)
            return
        days = days[:ncols]
        col_w = area.width // ncols
        label_font = get_font("4x6") if col_w >= 16 else get_font("tom-thumb")
        num_font = get_font("4x6") if col_w >= 16 else get_font("tom-thumb")
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

    def _forecast_rows(self, area: Canvas, fc: Forecast, now: datetime, days: list[Daily]) -> None:
        """Stacked rows for tall or narrow areas: icon on the left, day and hi/lo on the right."""
        text = self._text_color()
        n = max(1, min(len(days), area.height // 16))
        row_h = min(28, area.height // n)
        icon = _snap(min(row_h - 2, area.width // 2), (8, 12, 16, 24))
        label = get_font("4x6")
        small = get_font("4x6") if area.width - icon - 2 >= 24 else get_font("tom-thumb")
        for i, d in enumerate(days[:n]):
            row = area.sub(0, i * row_h, area.width, row_h)
            draw_weather_icon(row, 1, (row_h - icon) // 2, icon, icon_for(d.code), is_day=True)
            x = icon + 3
            avail = area.width - x
            row.text(x, (row_h - 6 - 2 * small.line_height - 2) // 2, d.date.strftime("%a"), label, text)
            y = (row_h - 6 - 2 * small.line_height - 2) // 2 + 7
            hi, lo = _hilo(d.tmax, d.tmin, small.name == "tom-thumb")
            if small.measure(hi) + 2 + small.measure(lo) <= avail:
                row.text(x, y, hi, small, HI_COLOR)
                row.text(x + small.measure(hi) + 3, y, lo, small, LO_COLOR)
            else:
                row.text(x, y, hi, small, HI_COLOR)
                row.text(x, y + small.line_height + 1, lo, small, LO_COLOR)

    # ---- generic (every other size) -------------------------------------------------------

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        got = self._frame(c, frame)
        if got is None:
            self._draw_status(c)
            return
        fc, area, now = got
        if self._page(frame) == "forecast":
            self._forecast_page(area, fc, now, icon=16 if area.height >= 40 else 8)
            return
        cur = fc.current
        text = self._text_color()
        w, h = area.width, area.height
        tall = h > w
        if tall:
            self._current_tall(area, fc, now)
            return
        icon = _snap(min(h - 4, w // 3), (8, 12, 16, 24, 32, 48))
        draw_weather_icon(area, 1, 1, icon, icon_for(cur.code, cur.is_day), is_day=cur.is_day)
        right_x = icon + 3
        right_w = w - right_x
        fonts = [get_font(n) for n in ("10x20", "9x15", "7x13B", "6x10", "5x8", "4x6")]
        fonts = [f for f in fonts if f.line_height <= max(8, icon)] or [get_font("4x6")]
        font, temp = fit_text(deg(cur.temp), fonts, right_w)
        today = fc.today()
        small = get_font("4x6") if w >= 40 else get_font("tom-thumb")
        tiny = small.name == "tom-thumb"
        label = label_for(cur.code, cur.is_day) if w >= 60 else short_label_for(cur.code, cur.is_day)
        spare = right_w - font.measure(temp) - 4
        if spare >= 40:
            # Wide (128x32, 128x64): temp next to the icon, condition + H/L in a column to the right.
            ty = 1 + max(0, (icon - font.line_height) // 2)
            area.text(right_x, ty, temp, font, text)
            col_x = right_x + font.measure(temp) + 6
            col_w = w - col_x
            big = [get_font(n) for n in ("10x20", "9x15", "7x13B", "6x10", "5x8")]
            cf, ctext = fit_text(label, [f for f in big if f.line_height <= (h - 4) // 2] or [small], col_w)
            hl = get_font("6x10") if h >= 48 else small
            block_h = cf.line_height + 2 + hl.line_height
            cy = max(0, (h - block_h) // 2)
            area.text(col_x, cy, ctext, cf, text)
            if today is not None:
                hi, lo = _hilo(today.tmax, today.tmin, hl.name == "tom-thumb")
                area.text(col_x, cy + cf.line_height + 2, hi, hl, HI_COLOR)
                area.text(col_x + hl.measure(hi) + 4, cy + cf.line_height + 2, lo, hl, LO_COLOR)
            return
        area.text(
            right_x + (right_w - font.measure(temp)) // 2, 1 + max(0, (icon - font.line_height) // 3), temp, font, text
        )
        y = 1 + icon + 2
        if today is not None and h - y >= small.line_height:
            hi, lo = _hilo(today.tmax, today.tmin, tiny)
            total = small.measure(hi) + 4 + small.measure(lo)
            x = (w - total) // 2
            area.text(x, y, hi, small, HI_COLOR)
            area.text(x + small.measure(hi) + 4, y, lo, small, LO_COLOR)
            y += small.line_height + 1
        if self.settings.show_condition and h - y >= small.line_height:
            f, label = fit_text(label, [small, get_font("tom-thumb")], w)
            area.text_centered(y, label, f, text)

    def _current_tall(self, area: Canvas, fc: Forecast, now: datetime) -> None:
        cur = fc.current
        text = self._text_color()
        w, h = area.width, area.height
        icon = _snap(min(w - 4, h // 3), (8, 12, 16, 24, 32, 48))
        draw_weather_icon(area, (w - icon) // 2, 2, icon, icon_for(cur.code, cur.is_day), is_day=cur.is_day)
        y = 2 + icon + 2
        font, temp = fit_text(deg(cur.temp), [get_font(n) for n in ("10x20", "9x15", "7x13B", "6x10", "5x8")], w)
        area.text_centered(y, temp, font, text)
        y += font.line_height + 2
        small = get_font("4x6")
        today = fc.today()
        if today is not None:
            hi, lo = _hilo(today.tmax, today.tmin, False)
            if small.measure(hi) + 3 + small.measure(lo) <= w:
                x = (w - small.measure(hi) - 3 - small.measure(lo)) // 2
                area.text(x, y, hi, small, HI_COLOR)
                area.text(x + small.measure(hi) + 3, y, lo, small, LO_COLOR)
                y += 8
            else:
                area.text_centered(y, hi, small, HI_COLOR)
                area.text_centered(y + 7, lo, small, LO_COLOR)
                y += 15
        if self.settings.show_condition and h - y >= 6:
            f, label = fit_text(short_label_for(cur.code, cur.is_day), [small, get_font("tom-thumb")], w)
            area.text_centered(y, label, f, text)
            y += f.line_height + 3
        days = self._upcoming_days(fc, now)
        if days and h - y >= 40:
            self._forecast_rows(area.sub(0, y, w, h - y), fc, now, days)


def _hilo(tmax: float, tmin: float, tiny: bool) -> tuple[str, str]:
    """High/low labels; the 3x5 font is too narrow for the degree sign, so drop it there."""
    if tiny:
        return f"H{round(tmax)}", f"L{round(tmin)}"
    return f"H{deg(tmax)}", f"L{deg(tmin)}"


def _snap(value: int, steps: tuple[int, ...]) -> int:
    best = steps[0]
    for s in steps:
        if s <= value:
            best = s
    return best
