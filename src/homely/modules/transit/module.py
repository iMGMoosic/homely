"""Transit: the next departures from a stop, one row per route with a countdown.

Real-time departures (the agency is tracking the vehicle) count down in minutes; timetable
departures show their clock time, dimmer, the way Metro Transit's own signs do.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.data.slot import DataSlot
from homely.modules.transit.providers import PROVIDERS, Departure, StopBoard, TransitError, TransitProvider
from homely.modules.transit.settings import TransitSettings
from homely.render.canvas import Canvas
from homely.render.color import AMBER, Color, dim, lift, parse_color, readable_on
from homely.render.fonts import get_font
from homely.render.fonts.bdf import BitmapFont
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.status import draw_status_card
from homely.render.text import ScrollingLabels

CACHE_KEY = "board"
SCROLL_FPS = 30
SCHEDULED_DIM = 0.6

# Metro Transit's line colors. Letter routes are the arterial rapid-bus lines (A Line, B Line...),
# which share the red of their branding.
LINE_COLORS: dict[str, Color] = {
    "blue": (0, 83, 160),
    "green": (0, 132, 61),
    "red": (237, 27, 46),
    "orange": (246, 138, 30),
    "gold": (255, 196, 37),
    "nstr": (120, 80, 170),
    "northstar": (120, 80, 170),
}
RAPID_BUS: Color = (237, 27, 46)
BADGE_CODES = {"blue": "BLU", "green": "GRN", "red": "RED", "orange": "ORG", "gold": "GLD", "northstar": "NST"}


@dataclass(frozen=True)
class Row:
    route: str
    destination: str
    times: tuple[Departure, ...]


def route_matches(dep: Departure, wanted: list[str]) -> bool:
    if not wanted:
        return True
    names = {dep.route.lower(), dep.route_id.lower()}
    return any(w.lower() in names for w in wanted)


def upcoming(board: StopBoard, settings: TransitSettings, now: datetime) -> list[Departure]:
    """Departures the rider could still catch, inside the look-ahead window."""
    earliest = now + timedelta(minutes=settings.walk_minutes)
    latest = now + timedelta(minutes=settings.max_minutes)
    # A real-time bus a few seconds "late" relative to our clock is still at the stop.
    grace = timedelta(seconds=30 if settings.walk_minutes == 0 else 0)
    return [d for d in board.departures if earliest - grace <= d.time <= latest and route_matches(d, settings.routes)]


def build_rows(departures: list[Departure], group: bool) -> list[Row]:
    if not group:
        return [Row(d.route, d.destination, (d,)) for d in departures]
    rows: dict[tuple[str, str], list[Departure]] = {}
    for d in departures:  # already in time order, so rows come out soonest-first
        rows.setdefault((d.route, d.direction), []).append(d)
    return [Row(route, deps[0].destination, tuple(deps)) for (route, _), deps in rows.items()]


def when_text(dep: Departure, now: datetime, time_format: str, tz: tzinfo) -> str:
    if dep.realtime:
        mins = int((dep.time - now).total_seconds() // 60)
        return "Due" if mins < 1 else f"{mins}m"
    local = dep.time.astimezone(tz)
    if time_format == "24h":
        return f"{local.hour}:{local.minute:02d}"
    return f"{local.hour % 12 or 12}:{local.minute:02d}"


def badge_text(route: str) -> str:
    """Rail lines go by color names; a three-letter code keeps their badge as narrow as a bus number."""
    return BADGE_CODES.get(route.strip().lower(), route)


def badge_color(route: str, bus: Color) -> Color:
    key = route.strip().lower()
    if key in LINE_COLORS:
        return LINE_COLORS[key]
    if len(key) == 1 and key.isalpha():
        return RAPID_BUS
    return bus


class TransitModule(Module[TransitSettings]):
    info = ModuleInfo(
        id="transit",
        name="Transit",
        description="Next buses and trains from a stop, with real-time countdowns (Metro Transit).",
        tier=Tier.WANT,
        icon="transit",
        default_duration_s=15,
        default_fps=1,
        min_size=Size(32, 32),
        allow_multiple=True,
    )
    Settings = TransitSettings

    def __init__(self, ctx: ModuleContext, settings: TransitSettings) -> None:
        super().__init__(ctx, settings)
        self.board: DataSlot[StopBoard] = DataSlot()
        self._provider: TransitProvider | None = None
        self._labels = ScrollingLabels()

    # ---- data --------------------------------------------------------------------------

    async def setup(self) -> None:
        self._provider = PROVIDERS[self.settings.provider](self.ctx.http)
        cached = self.ctx.cache.get(CACHE_KEY, max_age_s=3600)
        if cached:
            try:
                board = StopBoard.from_dict(cached["board"])
                if board.stop_id == self.settings.stop_id:
                    self.board.set(board, datetime.fromisoformat(cached["at"]))
            except (KeyError, ValueError, TypeError) as exc:
                self.ctx.log.debug("ignoring bad transit cache: %s", exc)
        self.ctx.poll("departures", timedelta(seconds=self.settings.refresh_seconds), self._fetch)

    async def on_settings_changed(self, settings: TransitSettings) -> None:
        old = self.settings
        self.settings = settings
        if self._provider is not None:
            self._provider = PROVIDERS[settings.provider](self.ctx.http)
        for p in self.ctx.pollers:
            p.every = timedelta(seconds=settings.refresh_seconds)
        if (settings.provider, settings.stop_id) != (old.provider, old.stop_id):
            self.board.clear()
            for p in self.ctx.pollers:
                p.trigger()
        self.ctx.invalidate()

    async def _fetch(self) -> None:
        stop = self.settings.stop_id
        if stop is None:
            return
        assert self._provider is not None
        try:
            board = await self._provider.departures(stop)
        except Exception as exc:
            self.board.fail(exc)
            raise
        now = self.ctx.now()
        self.board.set(board, now)
        self.ctx.cache.set(CACHE_KEY, {"board": board.to_dict(), "at": now.isoformat()})
        self.ctx.invalidate()

    def _stale_after(self) -> timedelta:
        return timedelta(seconds=max(180, 4 * self.settings.refresh_seconds))

    def rows(self, now: datetime) -> list[Row]:
        board = self.board.value
        if board is None:
            return []
        return build_rows(upcoming(board, self.settings, now), self.settings.group_by_route)

    def should_display(self) -> bool:
        return bool(self.rows(self.ctx.now())) or self._status_message() is not None

    def _status_message(self) -> tuple[str, str] | None:
        if self.settings.stop_id is None:
            return ("No stop", "pick one in settings")
        if isinstance(self.board.error, TransitError):
            return ("Stop not found", "check the stop number")
        if self.board.value is None and self.board.error is not None:
            return ("No departures", "check the network")
        return None  # loading, or simply nothing coming: skip the turn

    # ---- slot lifecycle -----------------------------------------------------------------

    def on_enter(self) -> None:
        self._labels.reset()

    def fps(self) -> int:
        """Countdowns only need 1 fps; a scrolling destination or alert needs a real frame rate."""
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

    def _clock_text(self, now: datetime) -> str:
        local = now.astimezone(self.ctx.location.tz)
        if self.settings.time_format == "24h":
            return f"{local.hour}:{local.minute:02d}"
        return f"{local.hour % 12 or 12}:{local.minute:02d}"

    @staticmethod
    def _fonts(w: int, h: int) -> tuple[BitmapFont, BitmapFont | None]:
        """(row font, destination font). A destination font means two-line rows: badge and
        times on top, destination underneath -- square and tall panels have the height but not
        the width to fit all three on one line."""
        if w >= 96 and h >= 96:
            return get_font("6x10"), get_font("5x8")
        if w >= 96 and h >= 64:
            return get_font("6x10"), None
        if w >= 96:
            return get_font("5x7"), None
        if h >= 48:
            return (get_font("5x8"), get_font("4x6")) if w >= 64 else (get_font("4x6"), get_font("tom-thumb"))
        return get_font("4x6"), None

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        text = parse_color(self.settings.text_color)
        board = self.board.value
        rows = self.rows(frame.now)
        if not rows:
            msg = self._status_message()
            if msg is not None:
                draw_status_card(c, *msg, text)
            return
        assert board is not None
        w, h = c.width, c.height
        y = 0
        if self.settings.show_header and h >= 24:
            y = self._header(c, board, frame.now) + 1
        font, dest_font = self._fonts(w, h)
        row_h = font.line_height + 1 + (dest_font.line_height + 2 if dest_font else 0)
        alerts = board.alerts if self.settings.show_alerts else []
        alert_font = dest_font or font
        if alerts and h - y >= row_h + alert_font.line_height + 1:
            ay = h - alert_font.line_height
            c.hline(0, ay - 1, w, dim(AMBER, 0.35))
            self._labels.draw(c, 0, ay, "  •  ".join(alerts), [alert_font], w, AMBER)
            h = ay - 1
        n = max(1, (h - y) // row_h)
        rows = rows[:n]
        badge_w = max(font.measure(badge_text(r.route)) for r in rows) + 2
        for i, row in enumerate(rows):
            self._row(c, row, y + i * row_h, font, dest_font, badge_w, frame.now, text)
        if self.board.is_stale(frame.now, self._stale_after()):
            c.pixel(0, c.height - 1, dim(AMBER, 0.5))

    def _header(self, c: Canvas, board: StopBoard, now: datetime) -> int:
        """Stop name on the left, the time on the right; returns the header's height."""
        font = get_font("4x6") if c.width >= 48 else get_font("tom-thumb")
        color = parse_color(self.settings.header_color)
        clock = self._clock_text(now) if c.width >= 64 else ""
        clock_w = font.measure(clock) + 3 if clock else 0
        label = self.settings.name.strip() or board.stop_name or f"Stop {board.stop_id}"
        self._labels.draw(c, 0, 0, label, [font], c.width - clock_w, color)
        if clock:
            c.text(c.width - font.measure(clock), 0, clock, font, dim(parse_color(self.settings.text_color), 0.7))
        return font.line_height

    def _row(
        self,
        c: Canvas,
        row: Row,
        y: int,
        font: BitmapFont,
        dest_font: BitmapFont | None,
        badge_w: int,
        now: datetime,
        text: Color,
    ) -> None:
        w = c.width
        fill = lift(badge_color(row.route, parse_color(self.settings.bus_color)), 0.55)
        label = badge_text(row.route)
        c.rect(0, y, badge_w, font.line_height, fill=fill)
        c.text(1 + (badge_w - 2 - font.measure(label)) // 2, y, label, font, readable_on(fill))
        gap = 2 if font.line_height <= 6 else 3
        dest_x = badge_w + gap
        max_times = 3 if w >= 96 else 2 if w >= 48 else 1
        deps = list(row.times[:max_times])
        times = [when_text(d, now, self.settings.time_format, self.ctx.location.tz) for d in deps]
        # On one line the destination shares the row: drop later times until it keeps a
        # readable width, but always keep the next departure.
        min_dest = 0 if dest_font else 8 * font.default_advance
        while len(times) > 1 and w - dest_x - self._times_w(times, font, gap) - gap < min_dest:
            times, deps = times[:-1], deps[:-1]
        times_w = self._times_w(times, font, gap)
        x = w - times_w
        for t, d in zip(times, deps, strict=True):
            c.text(x, y, t, font, text if d.realtime else dim(text, SCHEDULED_DIM))
            x += font.measure(t) + gap
        dest_color = dim(text, 0.8)
        if dest_font is not None:
            self._labels.draw(c, 0, y + font.line_height + 1, row.destination, [dest_font], w, dest_color)
            return
        dest_w = w - times_w - gap - dest_x
        if dest_w >= 3 * font.default_advance:
            self._labels.draw(c, dest_x, y, row.destination, [font], dest_w, dest_color)

    @staticmethod
    def _times_w(times: list[str], font: BitmapFont, gap: int) -> int:
        return sum(font.measure(t) for t in times) + gap * (len(times) - 1)
