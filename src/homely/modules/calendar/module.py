"""Calendar: upcoming events from ICS links, a day at a time.

Each page is headed by its day ("Today", "Tomorrow", "Sat 27") and lists that day's events with
a bar in the calendar's color. An event under way shows "now" instead of its start time.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.data.http import ConditionalFetcher
from homely.data.slot import DataSlot
from homely.modules.calendar.ics import Event, parse_ics
from homely.modules.calendar.settings import CalendarSettings
from homely.render.canvas import Canvas
from homely.render.color import AMBER, Color, dim, lift, parse_color
from homely.render.fonts import get_font
from homely.render.fonts.bdf import BitmapFont
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.status import draw_status_card
from homely.render.text import ScrollingLabels

CACHE_KEY = "events"
SCROLL_FPS = 30
NOW_COLOR: Color = (90, 230, 120)
STALE_AFTER = timedelta(hours=2)


@dataclass(frozen=True)
class Page:
    """One screenful: consecutive days, each with the events listed under it."""

    days: tuple[tuple[date, tuple[Event, ...]], ...]

    @property
    def first_day(self) -> date:
        return self.days[0][0]


def upcoming(events: list[Event], now: datetime, settings: CalendarSettings) -> list[Event]:
    horizon = now + timedelta(days=settings.days_ahead)
    return [e for e in events if e.end > now and e.start < horizon and (settings.show_all_day or not e.all_day)]


def event_day(e: Event, now: datetime, tz: tzinfo) -> date:
    """The day an event is listed under: its start, or today if it began earlier and is still on."""
    return max(e.start.astimezone(tz).date(), now.astimezone(tz).date())


def paginate(events: list[Event], avail_h: int, row_h: int, label_h: int, now: datetime, tz: tzinfo) -> list[Page]:
    """Pack events onto pages by height. The first day on a page is named by the page header;
    each further day on the same page costs a label row of ``label_h``."""
    by_day: dict[date, list[Event]] = {}
    for e in events:
        by_day.setdefault(event_day(e, now, tz), []).append(e)
    pages: list[Page] = []
    current: list[tuple[date, list[Event]]] = []
    used = 0
    for day in sorted(by_day):
        for e in by_day[day]:
            new_day = not current or current[-1][0] != day
            need = row_h + (label_h if new_day and current else 0)
            if current and used + need > avail_h:
                pages.append(Page(tuple((d, tuple(evs)) for d, evs in current)))
                current, used, new_day, need = [], 0, True, row_h
            if new_day:
                current.append((day, []))
            current[-1][1].append(e)
            used += need
    if current:
        pages.append(Page(tuple((d, tuple(evs)) for d, evs in current)))
    return pages


def day_label(day: date, today: date, roomy: bool) -> str:
    if day == today:
        return "Today"
    if day == today + timedelta(days=1):
        return "Tomorrow" if roomy else "Tmrw"
    if day - today < timedelta(days=7):
        return f"{day:%a} {day.day}"
    # Further out, the weekday and date alone would be ambiguous: name the month.
    return f"{day:%a} {day:%b} {day.day}" if roomy else f"{day:%b} {day.day}"


def clock_text(t: datetime, fmt: str) -> str:
    if fmt == "24h":
        return f"{t.hour}:{t.minute:02d}"
    h = t.hour % 12 or 12
    ampm = "a" if t.hour < 12 else "p"
    return f"{h}{ampm}" if t.minute == 0 else f"{h}:{t.minute:02d}{ampm}"


class CalendarModule(Module[CalendarSettings]):
    info = ModuleInfo(
        id="calendar",
        name="Calendar",
        description="Upcoming events from your calendars' ICS links (Google, iCloud, Outlook, ...).",
        tier=Tier.WANT,
        icon="calendar",
        default_duration_s=16,
        default_fps=1,
        min_size=Size(32, 32),
        allow_multiple=True,
    )
    Settings = CalendarSettings

    def __init__(self, ctx: ModuleContext, settings: CalendarSettings) -> None:
        super().__init__(ctx, settings)
        self.events: DataSlot[list[Event]] = DataSlot()
        self._fetcher: ConditionalFetcher | None = None
        self._per_url: dict[str, list[Event]] = {}
        self._turn: list[Page] = []
        self._labels = ScrollingLabels()

    # ---- data --------------------------------------------------------------------------

    async def setup(self) -> None:
        self._fetcher = ConditionalFetcher(self.ctx.http)
        cached = self.ctx.cache.get(CACHE_KEY, max_age_s=24 * 3600)
        if cached:
            try:
                self.events.set([Event.from_dict(d) for d in cached["events"]], datetime.fromisoformat(cached["at"]))
            except (KeyError, ValueError, TypeError) as exc:
                self.ctx.log.debug("ignoring bad calendar cache: %s", exc)
        self.ctx.poll("calendars", timedelta(minutes=self.settings.refresh_minutes), self._fetch)

    async def on_settings_changed(self, settings: CalendarSettings) -> None:
        old = self.settings
        self.settings = settings
        for p in self.ctx.pollers:
            p.every = timedelta(minutes=settings.refresh_minutes)
        if [(c.url, c.color) for c in settings.calendars] != [(c.url, c.color) for c in old.calendars] or (
            settings.days_ahead != old.days_ahead
        ):
            self._per_url = {}
            if self._fetcher is not None:
                for c in old.calendars:
                    self._fetcher.forget(c.url)
            if not settings.calendars:
                self.events.clear()
            for p in self.ctx.pollers:
                p.trigger()
        self.ctx.invalidate()

    async def _fetch(self) -> None:
        assert self._fetcher is not None
        if not self.settings.calendars:
            return
        tz = self.ctx.location.tz
        now = self.ctx.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = start + timedelta(days=self.settings.days_ahead + 2)
        errors = 0
        for cal in self.settings.calendars:
            try:
                body = await self._fetcher.fetch(cal.url)
                if body is None and cal.url in self._per_url:
                    continue  # unchanged since last time
                if body is None:
                    self._fetcher.forget(cal.url)
                    body = await self._fetcher.fetch(cal.url)
                assert body is not None
                self._per_url[cal.url] = await asyncio.to_thread(parse_ics, body, start, end, tz, cal.color)
            except Exception as exc:  # one broken link must not hide the other calendars
                errors += 1
                self.ctx.log.warning("calendar: %s failed: %s", cal.name or "a calendar", exc)
        if errors == len(self.settings.calendars):
            err = RuntimeError("no calendar could be loaded")
            self.events.fail(err)
            raise err
        urls = {c.url for c in self.settings.calendars}
        events = sorted(
            (e for u, evs in self._per_url.items() if u in urls for e in evs),
            key=lambda e: (e.start, not e.all_day, e.title),
        )
        self.events.set(events, now)
        self.ctx.cache.set(CACHE_KEY, {"events": [e.to_dict() for e in events], "at": now.isoformat()})
        self.ctx.invalidate()

    def _upcoming(self, now: datetime) -> list[Event]:
        return upcoming(self.events.value or [], now, self.settings)

    def should_display(self) -> bool:
        if self._status_message() is not None:
            return True
        if not self.events.has_value:
            return False
        return bool(self._upcoming(self.ctx.now())) or self.settings.show_when_empty

    def _status_message(self) -> tuple[str, str] | None:
        if not self.settings.calendars:
            return ("No calendar", "add an ICS link in settings")
        if not self.events.has_value and self.events.error is not None:
            return ("No calendar", "check the ICS link")
        return None

    # ---- slot lifecycle -----------------------------------------------------------------

    def on_enter(self) -> None:
        self._labels.reset()
        now = self.ctx.now()
        events = self._upcoming(now)[: self.settings.max_events]
        header_font, _, _, row_h = self._layout(self.ctx.size)
        avail = self.ctx.size.h - header_font.line_height - 1
        self._turn = paginate(events, avail, row_h, header_font.line_height + 1, now, self.ctx.location.tz)

    def duration(self) -> float:
        return float(max(1, len(self._turn)) * self.settings.seconds_per_page)

    def fps(self) -> int:
        probe = FrameInfo(
            now=self.ctx.now(), monotonic=0.0, dt=0.0, index=0, slot_elapsed=0.0, slot_duration=self.duration()
        )
        self._labels.scrolled = False
        self.render(Canvas(self.ctx.size), probe)
        return SCROLL_FPS if self._labels.scrolled else self.info.default_fps

    def render(self, canvas: Canvas, frame: FrameInfo) -> None:
        self._labels.advance(frame.dt)
        super().render(canvas, frame)

    # ---- render -----------------------------------------------------------------------

    @staticmethod
    def _layout(size: Size) -> tuple[BitmapFont, BitmapFont, BitmapFont | None, int]:
        """(header font, time font, title font for two-line rows or None, row height)."""
        w, h = size.w, size.h
        header = get_font("4x6") if w >= 48 else get_font("tom-thumb")
        if w >= 96 and h >= 96:
            time_f, title_f = get_font("5x8"), get_font("6x10")
        elif w >= 96 and h >= 64:
            time_f, title_f = get_font("6x10"), None
        elif w >= 96:
            time_f, title_f = get_font("5x7"), None
        elif w >= 64 and h >= 48:
            time_f, title_f = get_font("4x6"), get_font("5x8")
        elif w >= 64:
            time_f, title_f = get_font("4x6"), None
        else:
            # Too narrow for a time column beside the title: stack them.
            time_f, title_f = get_font("tom-thumb"), get_font("4x6")
        row_h = time_f.line_height + 1 + (title_f.line_height + 2 if title_f else 0)
        return header, time_f, title_f, row_h

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        text = parse_color(self.settings.text_color)
        msg = self._status_message()
        if msg is not None and not self.events.has_value:
            draw_status_card(c, *msg, text)
            return
        tz = self.ctx.location.tz
        now = frame.now.astimezone(tz)
        if not self._turn:
            self.on_enter()
        header_font, time_f, title_f, row_h = self._layout(c.size)
        if not self._turn:
            self._header(c, now.date(), now.date(), header_font)
            c.text_centered(
                header_font.line_height + (c.height - header_font.line_height) // 2 - 3,
                "Nothing coming up",
                get_font("4x6") if c.width >= 72 else get_font("tom-thumb"),
                dim(text, 0.6),
            )
            return
        pages = len(self._turn)
        index = min(pages - 1, int(frame.slot_elapsed // self.settings.seconds_per_page))
        page = self._turn[index]
        today = now.date()
        self._header(c, page.first_day, today, header_font)
        events = [e for _, evs in page.days for e in evs]
        time_w = max(time_f.measure(self._when(e, now, short=title_f is None)) for e in events)
        y = header_font.line_height + 1
        label_color = dim(parse_color(self.settings.header_color), 0.8)
        for k, (day, evs) in enumerate(page.days):
            if k > 0:
                c.text(0, y, day_label(day, today, c.width >= 48), header_font, label_color)
                y += header_font.line_height + 1
            for e in evs:
                self._event(c, e, self._when(e, now, short=title_f is None), y, time_f, title_f, time_w, now, text)
                y += row_h
        if pages > 1:
            x0 = c.width - pages * 2
            for k in range(pages):
                c.pixel(x0 + k * 2, c.height - 1, text if k == index else dim(text, 0.25))
        if self.events.is_stale(frame.now, STALE_AFTER):
            c.pixel(0, c.height - 1, dim(AMBER, 0.5))

    def _header(self, c: Canvas, day: date, today: date, font: BitmapFont) -> None:
        color = parse_color(self.settings.header_color)
        label = day_label(day, today, c.width >= 48)
        c.text(0, 0, label, font, color)
        date_text = f"{day:%b} {day.day}" if day in (today, today + timedelta(days=1)) else ""
        if date_text and font.measure(label) + font.measure(date_text) + 4 <= c.width:
            c.text(c.width - font.measure(date_text), 0, date_text, font, dim(color, 0.6))

    def _when(self, e: Event, now: datetime, *, short: bool) -> str:
        if e.all_day:
            return "all" if short else "all day"
        if e.start <= now < e.end:
            return "now"
        return clock_text(e.start.astimezone(now.tzinfo), self.settings.time_format)

    def _event(
        self,
        c: Canvas,
        e: Event,
        when: str,
        y: int,
        time_f: BitmapFont,
        title_f: BitmapFont | None,
        time_w: int,
        now: datetime,
        text: Color,
    ) -> None:
        color = lift(parse_color(e.color), 0.55)
        when_color = NOW_COLOR if when == "now" else dim(text, 0.75)
        if title_f is not None:
            # Two lines: a color bar and the time on top, the title underneath.
            c.rect(0, y, 2, time_f.line_height + 1 + title_f.line_height, fill=color)
            c.text(4, y, when, time_f, when_color)
            if not e.all_day:
                dash = "\u2013" if time_f.has("\u2013") else "-"  # en dash
                until = dash + clock_text(e.end.astimezone(now.tzinfo), self.settings.time_format)
                ex = 4 + time_f.measure(when)
                if ex + time_f.measure(until) <= c.width:
                    c.text(ex, y, until, time_f, dim(text, 0.5))
            self._labels.draw(c, 4, y + time_f.line_height + 1, e.title, [title_f], c.width - 4, text)
            return
        # One line: color bar, time column, title.
        c.rect(0, y, 2, time_f.line_height, fill=color)
        c.text(4, y, when, time_f, when_color)
        x = 4 + time_w + 3
        self._labels.draw(c, x, y, e.title, [time_f], c.width - x, text)
