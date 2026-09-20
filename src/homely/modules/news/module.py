"""News: headlines from RSS/Atom feeds, a few per turn, wrapped to fit the panel."""

from __future__ import annotations

from datetime import datetime, timedelta

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.data.slot import DataSlot
from homely.modules.news.feeds import FeedFetcher, Headline
from homely.modules.news.settings import NewsSettings
from homely.render.canvas import Canvas
from homely.render.color import Color, dim, parse_color
from homely.render.fonts import get_font
from homely.render.fonts.bdf import BitmapFont
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.text import Marquee, truncate, wrap_text

CACHE_KEY = "headlines"
STALE_AFTER = timedelta(hours=3)


def age_text(published: datetime | None, now: datetime) -> str:
    if published is None:
        return ""
    secs = max(0, int((now - published).total_seconds()))
    if secs < 3600:
        return f"{max(1, secs // 60)}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def order_headlines(per_source: dict[str, list[Headline]], mix: str) -> list[Headline]:
    lists = [sorted(items, key=_sort_key) for items in per_source.values()]
    if mix == "newest":
        return sorted((h for items in lists for h in items), key=_sort_key)
    out: list[Headline] = []
    i = 0
    while any(lists):
        for items in lists:
            if i < len(items):
                out.append(items[i])
        i += 1
        if all(i >= len(items) for items in lists):
            break
    return out


def _sort_key(h: Headline) -> float:
    return -(h.published.timestamp() if h.published else 0.0)


class NewsModule(Module[NewsSettings]):
    info = ModuleInfo(
        id="news",
        name="News",
        description="Headlines from any RSS or Atom feeds, a few per turn.",
        tier=Tier.NEED,
        icon="news",
        default_duration_s=30,
        default_fps=1,
        min_size=Size(32, 32),
    )
    Settings = NewsSettings

    def __init__(self, ctx: ModuleContext, settings: NewsSettings) -> None:
        super().__init__(ctx, settings)
        self.headlines: DataSlot[list[Headline]] = DataSlot()
        self._fetcher: FeedFetcher | None = None
        self._per_source: dict[str, list[Headline]] = {}
        self._cursor = 0
        self._current: list[Headline] = []
        self._marquees: list[Marquee] = []

    # ---- data --------------------------------------------------------------------------

    async def setup(self) -> None:
        self._fetcher = FeedFetcher(self.ctx.http)
        cached = self.ctx.cache.get(CACHE_KEY, max_age_s=12 * 3600)
        if cached:
            try:
                items = [Headline.from_dict(d) for d in cached["items"]]
                self.headlines.set(items, datetime.fromisoformat(cached["at"]))
            except (KeyError, ValueError, TypeError) as exc:
                self.ctx.log.debug("ignoring bad news cache: %s", exc)
        self.ctx.poll("feeds", timedelta(minutes=self.settings.refresh_minutes), self._fetch)

    async def on_settings_changed(self, settings: NewsSettings) -> None:
        feeds_changed = [f.url for f in settings.feeds] != [f.url for f in self.settings.feeds]
        self.settings = settings
        if feeds_changed:
            self._per_source = {}
            for p in self.ctx.pollers:
                p.trigger()
        self.ctx.invalidate()

    async def _fetch(self) -> None:
        assert self._fetcher is not None
        now = self.ctx.now()
        cutoff = now - timedelta(hours=self.settings.max_age_hours)
        errors = 0
        for feed in self.settings.feeds:
            try:
                result = await self._fetcher.fetch_and_parse(feed.url, source_name=feed.name, color=feed.color)
            except Exception as exc:  # one bad feed must not sink the others
                errors += 1
                self.ctx.log.warning("news: %s failed: %s", feed.url, exc)
                continue
            if result is None:
                continue  # unchanged
            _, items = result
            self._per_source[feed.url] = [h for h in items if h.published is None or h.published >= cutoff]
        active = {f.url for f in self.settings.feeds}
        ordered = order_headlines({u: v for u, v in self._per_source.items() if u in active}, self.settings.mix)
        if ordered:
            self.headlines.set(ordered, now)
            self.ctx.cache.set(CACHE_KEY, {"items": [h.to_dict() for h in ordered], "at": now.isoformat()})
            self.ctx.invalidate()
        elif errors:
            raise RuntimeError(f"{errors} feed(s) failed")

    def should_display(self) -> bool:
        return bool(self.headlines.value)

    # ---- slot lifecycle -----------------------------------------------------------------

    def on_enter(self) -> None:
        items = self.headlines.value or []
        n = min(self.settings.headlines_per_slot, len(items))
        if n == 0:
            self._current = []
            return
        start = self._cursor % len(items)
        self._current = [items[(start + i) % len(items)] for i in range(n)]
        self._cursor = (start + n) % len(items)
        self._marquees = []
        if self._marquee_mode(self.ctx.size):
            font = get_font("4x6")
            self._marquees = [Marquee(h.title, font, self.ctx.size.w, speed=18, gap=12) for h in self._current]

    def duration(self) -> float:
        n = max(1, len(self._current) or min(self.settings.headlines_per_slot, len(self.headlines.value or [])))
        return float(n * self.settings.seconds_per_headline)

    def fps(self) -> int:
        return 30 if self._marquee_mode(self.ctx.size) else 1

    @staticmethod
    def _marquee_mode(size: Size) -> bool:
        """Tiny wide panels scroll one line; anything with height wraps instead."""
        return size.w < 48 and size.h < 48

    def _index(self, frame: FrameInfo) -> int:
        if not self._current:
            return 0
        return min(len(self._current) - 1, int(frame.slot_elapsed // self.settings.seconds_per_headline))

    # ---- render -----------------------------------------------------------------------

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if not self._current:
            self.on_enter()
        if not self._current:
            return
        i = self._index(frame)
        h = self._current[i]
        text = parse_color(self.settings.text_color)
        src_color = parse_color(h.color)
        w, hgt = c.width, c.height
        header_font = get_font("4x6") if w >= 48 else get_font("tom-thumb")
        age = age_text(h.published, frame.now) if self.settings.show_age else ""
        age_w = header_font.measure(age) + 2 if age else 0
        c.text(1, 0, truncate(h.source, header_font, w - 2 - age_w), header_font, src_color)
        if age:
            c.text(w - header_font.measure(age) - 1, 0, age, header_font, dim(text, 0.55))
        rule_y = header_font.line_height
        c.hline(0, rule_y, w, dim(src_color, 0.6))
        dots_h = 3 if len(self._current) > 1 and hgt >= 40 else 0
        body_y = rule_y + 2
        body_h = hgt - body_y - dots_h
        if self._marquees:
            m = self._marquees[i]
            m.advance(frame.dt)
            m.draw(c, 0, body_y + (body_h - m.font.line_height) // 2, text)
        else:
            pad = 1 if w >= 48 else 0
            self._draw_wrapped(c.sub(pad, body_y, w - 2 * pad, body_h), h.title, text)
        if dots_h:
            n = len(self._current)
            x0 = (w - (n * 3 - 1)) // 2
            for k in range(n):
                c.rect(x0 + k * 3, hgt - 2, 2, 1, fill=text if k == i else dim(text, 0.3))
        if self.headlines.is_stale(frame.now, STALE_AFTER):
            c.pixel(0, hgt - 1, dim((255, 176, 0), 0.5))

    @staticmethod
    def _draw_wrapped(area: Canvas, title: str, color: Color) -> None:
        names: tuple[str, ...] = ("6x10", "5x8", "4x6", "tom-thumb")
        if area.height >= 90 and area.width >= 90:
            names = ("9x15", "7x13B", *names)
        fonts: list[BitmapFont] = [get_font(n) for n in names]
        chosen: tuple[BitmapFont, list[str]] | None = None
        words = title.split()
        for font in fonts:
            max_lines = area.height // (font.line_height + 1)
            if max_lines < 1:
                continue
            if font is not fonts[-1] and any(font.measure(word) > area.width for word in words):
                continue  # this font would split a word; try a smaller one
            lines = wrap_text(title, font, area.width)
            if len(lines) <= max_lines:
                chosen = (font, lines)
                break
        if chosen is None:
            font = fonts[-2] if area.height >= 14 else fonts[-1]
            max_lines = max(1, area.height // (font.line_height + 1))
            chosen = (font, wrap_text(title, font, area.width, max_lines=max_lines))
        font, lines = chosen
        step = font.line_height + 1
        total = len(lines) * step - 1
        y = max(0, (area.height - total) // 2) if len(lines) > 1 else max(0, (area.height - font.line_height) // 2)
        for line in lines:
            area.text(0, y, line, font, color)
            y += step
