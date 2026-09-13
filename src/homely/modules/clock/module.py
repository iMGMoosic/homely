"""Clock: the first module. Seven-segment LCD-style digits by default, pixel fonts optionally."""

from __future__ import annotations

from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.clock.settings import ClockSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, parse_color
from homely.render.fonts import get_font
from homely.render.layout import layout, layout_fallback
from homely.render.segments import SegmentFont, fit_segment_font
from homely.render.size import Size
from homely.render.text import fit_text

GHOST_DIM = 0.08


class ClockModule(Module[ClockSettings]):
    info = ModuleInfo(
        id="clock",
        name="Clock",
        description="Time and date, LCD-clock style or pixel font, in your colors.",
        tier=Tier.NEED,
        icon="clock",
        default_duration_s=15,
        default_fps=2,
        min_size=Size(32, 32),
        can_overlay=True,
    )
    Settings = ClockSettings

    def __init__(self, ctx: ModuleContext, settings: ClockSettings) -> None:
        super().__init__(ctx, settings)
        self._tz: tzinfo | None = None
        self._apply_tz()

    def _apply_tz(self) -> None:
        self._tz = None
        if self.settings.timezone:
            try:
                self._tz = ZoneInfo(self.settings.timezone)
            except (ZoneInfoNotFoundError, ValueError):
                self.ctx.log.warning("clock: unknown timezone %r", self.settings.timezone)

    async def on_settings_changed(self, settings: ClockSettings) -> None:
        self.settings = settings
        self._apply_tz()
        self.ctx.invalidate()

    def fps(self) -> int:
        return 2 if (self.settings.show_seconds or self.settings.blink_colon) else 1

    # ---- formatting helpers -------------------------------------------------------

    def now(self, frame: FrameInfo) -> datetime:
        return frame.now.astimezone(self._tz) if self._tz is not None else frame.now

    def hour_text(self, now: datetime) -> str:
        """Hour digits for pixel style: no padding unless leading_zero or 24h."""
        s = self.settings
        hour = now.hour
        if s.time_format == "12h":
            hour = hour % 12 or 12
        return f"{hour:02d}" if s.leading_zero or s.time_format == "24h" else str(hour)

    def time_digits(self, now: datetime) -> str:
        """Fixed-width 'HH:MM' for segment style; a blank leading digit like a real clock."""
        s = self.settings
        hour = now.hour
        if s.time_format == "12h":
            hour = hour % 12 or 12
        hh = f"{hour:02d}" if (s.leading_zero or s.time_format == "24h") else f"{hour:2d}"
        return f"{hh}:{now.minute:02d}"

    def ampm(self, now: datetime) -> str:
        if self.settings.time_format != "12h" or not self.settings.show_ampm:
            return ""
        return "AM" if now.hour < 12 else "PM"

    def colon_visible(self, frame: FrameInfo) -> bool:
        if not self.settings.blink_colon:
            return True
        return int(frame.monotonic * 2) % 2 == 0

    def date_text(self, now: datetime) -> str:
        return self.date_variants(now)[0] if self.settings.show_date else ""

    def date_variants(self, now: datetime) -> list[str]:
        """Preferred date text first, then progressively shorter fallbacks for narrow panels."""
        fmt = self.settings.date_format
        if fmt == "weekday_month_day":
            return [now.strftime("%a %b ") + str(now.day), now.strftime("%b ") + str(now.day), f"{now.month}/{now.day}"]
        if fmt == "month_day":
            return [now.strftime("%b ") + str(now.day), f"{now.month}/{now.day}"]
        if fmt == "day_month":
            return [f"{now.day} " + now.strftime("%b"), f"{now.day}/{now.month}"]
        if fmt == "iso":
            return [now.strftime("%Y-%m-%d"), now.strftime("%m-%d")]
        return [""]

    def colors(self) -> tuple[Color, Color, Color]:
        s = self.settings
        return parse_color(s.time_color), parse_color(s.date_color), parse_color(s.accent_color)

    def ghost(self, color: Color) -> Color | None:
        return dim(color, GHOST_DIM) if self.settings.ghost_segments else None

    def _draw_date(
        self, c: Canvas, y: int, now: datetime, font_names: tuple[str, ...], max_w: int, color: Color
    ) -> None:
        fonts = [get_font(n) for n in font_names]
        for variant in self.date_variants(now):
            for font in fonts:
                if font.measure(variant) <= max_w:
                    c.text_centered(y, variant, font, color)
                    return
        font, text = fit_text(self.date_variants(now)[-1], fonts, max_w)
        c.text_centered(y, text, font, color)

    def _draw_time_pixel(
        self, c: Canvas, x_center: int, y: int, font_name: str, now: datetime, frame: FrameInfo, color: Color
    ) -> tuple[int, int]:
        """Pixel-font HH:MM centered at x_center; returns (left x, right x)."""
        font = get_font(font_name)
        hh, mm = self.hour_text(now), f"{now.minute:02d}"
        total = font.measure(hh) + font.measure(":") + font.measure(mm)
        x = x_center - total // 2
        c.text(x, y, hh, font, color)
        colon_x = x + font.measure(hh)
        if self.colon_visible(frame):
            c.text(colon_x, y, ":", font, color)
        c.text(colon_x + font.measure(":"), y, mm, font, color)
        return x, x + total

    def _draw_time_segments(
        self, c: Canvas, x: int, y: int, font: SegmentFont, now: datetime, frame: FrameInfo, color: Color
    ) -> int:
        return font.draw(
            c, x, y, self.time_digits(now), color, off=self.ghost(color), colon_visible=self.colon_visible(frame)
        )

    def _seconds_ampm_row(self, c: Canvas, y: int, right: int, now: datetime, accent: Color, seg_h: int) -> None:
        """Seconds (small segments) right-aligned to `right`, AM/PM just left of them."""
        parts_w = 0
        sec_font: SegmentFont | None = None
        if self.settings.show_seconds:
            sec_font = fit_segment_font("88", 20, seg_h)
            parts_w += sec_font.measure("88")
        ampm = self.ampm(now)
        f46 = get_font("4x6")
        if ampm:
            parts_w += f46.measure(ampm) + (2 if sec_font else 0)
        x = right - parts_w
        if ampm:
            c.text(x, y + max(0, seg_h - f46.line_height) // 2 + (1 if seg_h > 8 else 0), ampm, f46, accent)
            x += f46.measure(ampm) + 2
        if sec_font:
            sec_font.draw(c, x, y, f"{now.second:02d}", accent, off=self.ghost(accent))

    # ---- segment layouts -----------------------------------------------------------

    def _seg_64x64(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        font = fit_segment_font("88:88", 60, 24)  # 12x22 t=2 -> 58 px wide
        x = (64 - font.measure("88:88")) // 2
        self._draw_time_segments(c, x, 5, font, now, frame, time_color)
        row_y = 31
        if self.settings.show_seconds or self.ampm(now):
            self._seconds_ampm_row(c, row_y, x + font.measure("88:88"), now, accent, 10)
        else:
            c.hline(x, row_y + 4, font.measure("88:88"), accent)
        if self.settings.show_date:
            self._draw_date(c, 48, now, ("6x10", "5x8", "4x6"), 62, date_color)

    def _seg_64x32(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        has_date = self.settings.show_date
        font = fit_segment_font("88:88", 44, 14)  # 8x14 t=2 -> 42 px
        y = 2 if has_date else 9
        w = self._draw_time_segments(c, 2, y, font, now, frame, time_color)
        col_x = 2 + w + 3
        ampm = self.ampm(now)
        if ampm:
            c.text(col_x, y, ampm, get_font("4x6"), accent)
        if self.settings.show_seconds:
            sec = fit_segment_font("88", 62 - col_x, 7)
            sec.draw(c, col_x, y + font.h - sec.h, f"{now.second:02d}", accent, off=self.ghost(accent))
        if has_date:
            self._draw_date(c, 22, now, ("5x8", "4x6", "tom-thumb"), 62, date_color)

    def _seg_32x32(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        font = fit_segment_font("88:88", 30, 10)  # 6x10 t=1 -> 29 px
        x = (32 - font.measure("88:88")) // 2
        self._draw_time_segments(c, x, 2, font, now, frame, time_color)
        # Row 2: "56 PM" as one centered group.
        tt = get_font("tom-thumb")
        ampm = self.ampm(now)
        parts: list[tuple[str, int]] = []
        sec_font = fit_segment_font("88", 12, 6) if self.settings.show_seconds else None
        total = (sec_font.measure("88") if sec_font else 0) + (tt.measure(ampm) if ampm else 0)
        if sec_font and ampm:
            total += 2
        px = (32 - total) // 2
        if sec_font:
            sec_font.draw(c, px, 14, f"{now.second:02d}", accent, off=self.ghost(accent))
            px += sec_font.measure("88") + 2
        if ampm:
            c.text(px, 14, ampm, tt, accent)
        del parts
        if self.settings.show_date:
            self._draw_date(c, 24, now, ("4x6", "tom-thumb"), 32, date_color)

    def _seg_32x64(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        font = fit_segment_font("88", 30, 22)  # 12x22 -> 26 px
        digits = self.time_digits(now)
        hh, mm = digits[:2], digits[3:]
        x = (32 - font.measure("88")) // 2
        font.draw(c, x, 3, hh, time_color, off=self.ghost(time_color))
        font.draw(c, x, 29, mm, time_color, off=self.ghost(time_color))
        dot = time_color if self.colon_visible(frame) else self.ghost(time_color)
        if dot is not None:
            c.rect(13, 26, 2, 2, fill=dot)
            c.rect(17, 26, 2, 2, fill=dot)
        tt = get_font("tom-thumb")
        ampm = self.ampm(now)
        sec_font = fit_segment_font("88", 14, 6) if self.settings.show_seconds else None
        total = (
            (sec_font.measure("88") if sec_font else 0)
            + (tt.measure(ampm) if ampm else 0)
            + (2 if sec_font and ampm else 0)
        )
        px = (32 - total) // 2
        if sec_font:
            sec_font.draw(c, px, 52, f"{now.second:02d}", accent, off=self.ghost(accent))
            px += sec_font.measure("88") + 2
        if ampm:
            c.text(px, 52, ampm, tt, accent)
        if self.settings.show_date:
            self._draw_date(c, 58, now, ("4x6", "tom-thumb"), 32, date_color)

    def _seg_any(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        has_date = self.settings.show_date and c.height >= 24
        font = fit_segment_font("88:88", c.width - 2, max(5, int(c.height * (0.45 if has_date else 0.7))))
        block_h = font.h + (8 if has_date else 0) + (8 if (self.settings.show_seconds or self.ampm(now)) else 0)
        y = max(0, (c.height - block_h) // 2)
        x = (c.width - font.measure("88:88")) // 2
        self._draw_time_segments(c, x, y, font, now, frame, time_color)
        y += font.h + 2
        if self.settings.show_seconds or self.ampm(now):
            self._seconds_ampm_row(c, y, x + font.measure("88:88"), now, accent, 6)
            y += 8
        if has_date:
            self._draw_date(c, y, now, ("6x10", "5x8", "4x6", "tom-thumb"), c.width - 2, date_color)

    # ---- pixel layouts ---------------------------------------------------------------

    def _pix_64x64(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        _, right = self._draw_time_pixel(c, 32, 4, "10x20", now, frame, time_color)
        ampm = self.ampm(now)
        if ampm:
            f46 = get_font("4x6")
            c.text(min(right + 2, 64 - f46.measure(ampm)), 18, ampm, f46, accent)
        if self.settings.show_seconds:
            c.text_centered(26, f"{now.second:02d}", get_font("7x13B"), accent)
        else:
            c.hline(8, 30, 48, accent)
        if self.settings.show_date:
            self._draw_date(c, 42, now, ("6x10", "5x8", "4x6"), 62, date_color)

    def _pix_64x32(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        has_date = self.settings.show_date
        y = 2 if has_date else 9
        _, right = self._draw_time_pixel(c, 32, y, "7x13B", now, frame, time_color)
        f46 = get_font("4x6")
        ampm = self.ampm(now)
        col_x = min(right + 2, 64 - 8)
        if ampm:
            c.text(col_x, y, ampm, f46, accent)
        if self.settings.show_seconds:
            c.text(col_x, y + 7, f"{now.second:02d}", f46, accent)
        if has_date:
            self._draw_date(c, 21, now, ("5x8", "4x6", "tom-thumb"), 62, date_color)

    def _pix_32x32(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        self._draw_time_pixel(c, 16, 3, "5x8", now, frame, time_color)
        tt = get_font("tom-thumb")
        ampm = self.ampm(now)
        secs = f"{now.second:02d}" if self.settings.show_seconds else ""
        row = " ".join(p for p in (secs, ampm) if p)
        if row:
            c.text_centered(14, row, tt, accent)
        if self.settings.show_date:
            self._draw_date(c, 24, now, ("4x6", "tom-thumb"), 32, date_color)

    def _pix_32x64(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        font = get_font("10x20")
        c.text_centered(6, self.hour_text(now), font, time_color)
        c.text_centered(28, f"{now.minute:02d}", font, time_color)
        if self.colon_visible(frame):
            c.rect(14, 26, 2, 1, fill=accent)
            c.rect(16, 26, 2, 1, fill=accent)
        tt = get_font("tom-thumb")
        ampm = self.ampm(now)
        secs = f"{now.second:02d}" if self.settings.show_seconds else ""
        row = " ".join(p for p in (secs, ampm) if p)
        if row:
            c.text_centered(50, row, tt, accent)
        if self.settings.show_date:
            self._draw_date(c, 57, now, ("4x6", "tom-thumb"), 32, date_color)

    def _pix_any(self, c: Canvas, frame: FrameInfo) -> None:
        now = self.now(frame)
        time_color, date_color, accent = self.colors()
        candidates = [get_font(n) for n in ("10x20", "9x15", "7x13B", "6x10", "5x8", "4x6")]
        time_text = f"{self.hour_text(now)}:{now.minute:02d}"
        font, _ = fit_text(time_text, candidates, c.width - 2)
        has_date = self.settings.show_date and c.height >= font.line_height + 8
        block_h = font.line_height + (8 if has_date else 0)
        y = max(0, (c.height - block_h) // 2)
        self._draw_time_pixel(c, c.width // 2, y, font.name, now, frame, time_color)
        if has_date:
            self._draw_date(
                c, y + font.line_height + 1, now, ("6x10", "5x8", "4x6", "tom-thumb"), c.width - 2, date_color
            )
        ampm = self.ampm(now)
        if ampm and c.width >= 48:
            c.text(c.width - 9, y, ampm, get_font("4x6"), accent)

    # ---- dispatch -------------------------------------------------------------------

    @property
    def _segment(self) -> bool:
        return self.settings.style == "segment"

    @layout(64, 64)
    def render_64x64(self, c: Canvas, frame: FrameInfo) -> None:
        (self._seg_64x64 if self._segment else self._pix_64x64)(c, frame)

    @layout(64, 32)
    def render_64x32(self, c: Canvas, frame: FrameInfo) -> None:
        (self._seg_64x32 if self._segment else self._pix_64x32)(c, frame)

    @layout(32, 32)
    def render_32x32(self, c: Canvas, frame: FrameInfo) -> None:
        (self._seg_32x32 if self._segment else self._pix_32x32)(c, frame)

    @layout(32, 64)
    def render_32x64(self, c: Canvas, frame: FrameInfo) -> None:
        (self._seg_32x64 if self._segment else self._pix_32x64)(c, frame)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        (self._seg_any if self._segment else self._pix_any)(c, frame)
