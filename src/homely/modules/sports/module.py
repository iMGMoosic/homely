"""Sports: today's scores, favorite teams first, as many game cards as fit on the panel.

A 128x32 board shows two 64x32 cards side by side; square and tall boards stack them. Scores
refresh every 30 seconds while a game you would see is live or about to start, and every few
minutes otherwise.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, tzinfo

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.data.slot import DataSlot
from homely.modules.sports.providers import LEAGUES, Game, SportsProvider, Team, make_provider, palette_for
from homely.modules.sports.settings import SportsSettings
from homely.render.canvas import Canvas
from homely.render.color import AMBER, Color, dim, luminance, parse_color
from homely.render.fonts import get_font
from homely.render.fonts.bdf import BitmapFont
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.status import draw_status_card
from homely.render.text import fit_text

CACHE_KEY = "games"
POLL_EVERY = timedelta(seconds=30)
HOT_WINDOW = timedelta(minutes=15)  # refresh fast from this long before the first pitch / puck drop
DAY_ROLLOVER = timedelta(hours=5)  # a game that runs past midnight is still "today" until 5 AM
STALE_AFTER = timedelta(minutes=30)
STATE_RANK = {"live": 0, "pre": 1, "final": 2, "off": 3}
BASE_ON: Color = (255, 200, 40)
OUT_ON: Color = (255, 70, 60)
LOSER_DIM = 0.35  # how much of a losing team's band and bar is left on a final
LOSER_TEXT: Color = (120, 120, 120)
LOSER_TEXT_ON_LIGHT: Color = (30, 30, 30)  # a white band dimmed is mid grey: grey text vanishes on it
BLACKISH = 40  # a band darker than this in every channel is black on the panel
TEAM_FONTS = ("10x20", "9x15", "7x13B", "6x10", "5x8", "4x6")


def parse_favorites(items: list[str]) -> list[tuple[str | None, str]]:
    out: list[tuple[str | None, str]] = []
    for raw in items:
        league, sep, team = raw.partition(":")
        if sep and league.strip().lower() in LEAGUES:
            out.append((league.strip().lower(), team.strip().lower()))
        else:
            out.append((None, raw.strip().lower()))
    return out


def team_matches(team: Team, token: str) -> bool:
    return token in (team.abbr.lower(), team.name.lower())


def is_favorite(game: Game, favorites: list[tuple[str | None, str]]) -> bool:
    return any(
        (league is None or league == game.league) and any(team_matches(t, token) for t in game.teams())
        for league, token in favorites
    )


def order_games(games: list[Game], settings: SportsSettings) -> list[tuple[Game, bool]]:
    """(game, is_favorite) pairs in display order: favorites, then live, upcoming, final."""
    favorites = parse_favorites(settings.favorites)
    out: list[tuple[Game, bool]] = []
    for g in games:
        fav = is_favorite(g, favorites)
        if settings.show == "favorites_only" and not fav:
            continue
        if g.state == "pre" and not settings.show_upcoming:
            continue
        if g.state == "final" and not settings.show_finals:
            continue
        if g.state == "off" and not fav:
            continue  # a postponement only matters if it is your team
        out.append((g, fav))
    first = settings.show != "all"
    out.sort(key=lambda gf: (0 if gf[1] and first else 1, STATE_RANK[gf[0].state], gf[0].start, gf[0].id))
    return out


def game_day(now: datetime, tz: tzinfo) -> date:
    return (now.astimezone(tz) - DAY_ROLLOVER).date()


def grid(size: Size) -> tuple[int, int]:
    """(columns, rows) of game cards for a panel size."""
    if size.w >= 128 and size.h >= 128:
        return 2, 2
    return max(1, size.w // 64), max(1, size.h // 32)


class SportsModule(Module[SportsSettings]):
    info = ModuleInfo(
        id="sports",
        name="Sports",
        description="Today's scores, favorite teams first: MLB, NFL, NBA, WNBA, NHL, MLS, Premier League.",
        tier=Tier.WANT,
        icon="sports",
        default_duration_s=18,
        default_fps=1,
        min_size=Size(32, 32),
        allow_multiple=True,
    )
    Settings = SportsSettings

    def __init__(self, ctx: ModuleContext, settings: SportsSettings) -> None:
        super().__init__(ctx, settings)
        self.games: DataSlot[list[Game]] = DataSlot()
        self._providers: dict[str, SportsProvider] = {}
        self._per_league: dict[str, list[Game]] = {}
        self._fetched: dict[str, tuple[datetime, date]] = {}
        self._turn: list[tuple[Game, bool]] = []
        self._cursor = 0

    # ---- data --------------------------------------------------------------------------

    async def setup(self) -> None:
        cached = self.ctx.cache.get(CACHE_KEY, max_age_s=6 * 3600)
        if cached:
            try:
                games = [Game.from_dict(d) for d in cached["games"]]
                self.games.set(games, datetime.fromisoformat(cached["at"]))
            except (KeyError, ValueError, TypeError) as exc:
                self.ctx.log.debug("ignoring bad sports cache: %s", exc)
        self.ctx.poll("scores", POLL_EVERY, self._fetch)

    async def on_settings_changed(self, settings: SportsSettings) -> None:
        added = set(settings.leagues()) - set(self.settings.leagues())
        self.settings = settings
        if added:
            for p in self.ctx.pollers:
                p.trigger()
        self._publish(self.ctx.now())
        self.ctx.invalidate()

    def _provider(self, league: str) -> SportsProvider:
        if league not in self._providers:
            self._providers[league] = make_provider(league, self.ctx.http)
        return self._providers[league]

    def _due(self, league: str, now: datetime, day: date) -> bool:
        last = self._fetched.get(league)
        if last is None or last[1] != day:
            return True
        age = now - last[0]
        if age >= timedelta(minutes=self.settings.refresh_minutes):
            return True
        shown = {g.id for g, _ in order_games(self._per_league.get(league, []), self.settings)}
        hot = any(
            g.id in shown and (g.state == "live" or (g.state == "pre" and g.start - now <= HOT_WINDOW))
            for g in self._per_league.get(league, [])
        )
        return hot and age >= POLL_EVERY - timedelta(seconds=5)

    async def _fetch(self) -> None:
        now = self.ctx.now()
        day = game_day(now, self.ctx.location.tz)
        errors: list[str] = []
        fetched = False
        for league in self.settings.leagues():
            if not self._due(league, now, day):
                continue
            try:
                games = await self._provider(league).games(day)
            except Exception as exc:  # one league's outage must not hide the others
                errors.append(league)
                self.ctx.log.warning("sports: %s failed: %s", league, exc)
                continue
            self._per_league[league] = games
            self._fetched[league] = (now, day)
            fetched = True
        if fetched:
            self._publish(now)
        elif errors and not self.games.has_value:
            err = RuntimeError(f"scores unavailable ({', '.join(errors)})")
            self.games.fail(err)
            raise err

    def _publish(self, now: datetime) -> None:
        enabled = set(self.settings.leagues())
        if not self._per_league:
            return
        games = [g for lg, gs in self._per_league.items() if lg in enabled for g in gs]
        self.games.set(games, now)
        self.ctx.cache.set(CACHE_KEY, {"games": [g.to_dict() for g in games], "at": now.isoformat()})
        self.ctx.invalidate()

    def visible(self) -> list[tuple[Game, bool]]:
        enabled = set(self.settings.leagues())
        return order_games([g for g in self.games.value or [] if g.league in enabled], self.settings)

    def should_display(self) -> bool:
        return bool(self.visible()) or self._status_message() is not None

    def _status_message(self) -> tuple[str, str] | None:
        if not self.settings.leagues():
            return ("No leagues", "pick some in settings")
        if not self.games.has_value and self.games.error is not None:
            return ("No scores", "check the network")
        return None

    # ---- slot lifecycle -----------------------------------------------------------------

    def on_enter(self) -> None:
        """Pick this turn's games: every favorite, then the rest in turns across rotations."""
        games = self.visible()
        limit = self.settings.max_games
        favs = [gf for gf in games if gf[1] and self.settings.show != "all"][:limit]
        rest = [gf for gf in games if gf not in favs]
        room = limit - len(favs)
        if rest and room > 0:
            start = self._cursor % len(rest)
            take = min(room, len(rest))
            picked = [rest[(start + i) % len(rest)] for i in range(take)]
            picked.sort(key=lambda gf: games.index(gf))
            self._cursor = (start + take) % len(rest)
        else:
            picked = []
        self._turn = favs + picked

    def _per_page(self) -> int:
        cols, rows = grid(self.ctx.size)
        return cols * rows

    def duration(self) -> float:
        n = len(self._turn) or min(self.settings.max_games, len(self.visible()))
        pages = max(1, math.ceil(n / self._per_page()))
        return float(pages * self.settings.seconds_per_page)

    # ---- render -----------------------------------------------------------------------

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        text = parse_color(self.settings.text_color)
        if not self._turn:
            self.on_enter()
        if not self._turn:
            msg = self._status_message()
            if msg is not None:
                draw_status_card(c, *msg, text)
            return
        cols, rows = grid(c.size)
        per = cols * rows
        n = len(self._turn)
        pages = max(1, math.ceil(n / per))
        page = min(pages - 1, int(frame.slot_elapsed // self.settings.seconds_per_page))
        if n >= per:
            # The last page tops itself up from the start of the list rather than leaving holes.
            games = [self._turn[(page * per + k) % n] for k in range(per)]
        else:
            # Fewer games than slots: fewer, bigger cards that still fill the panel.
            games = list(self._turn)
            cols = min(cols, n) if rows == 1 or n > rows else 1
            rows = math.ceil(n / cols)
        cw, ch = c.width // cols, c.height // rows
        multi = len(self.settings.leagues()) > 1
        for i, (game, _) in enumerate(games):
            col, row = i % cols, i // cols
            w = cw - (1 if col < cols - 1 else 0)
            h = ch - (1 if row < rows - 1 else 0)
            self._card(c.sub(col * cw, row * ch, w, h), game, frame.now, text, multi)
        if pages > 1 and c.height >= 32:
            self._page_dots(c, page, pages, text)
        if self.games.is_stale(frame.now, STALE_AFTER):
            c.pixel(0, c.height - 1, dim(AMBER, 0.5))

    def _page_dots(self, c: Canvas, page: int, pages: int, text: Color) -> None:
        x0 = c.width - pages * 2
        for k in range(pages):
            c.pixel(x0 + k * 2, c.height - 1, text if k == page else dim(text, 0.25))

    @staticmethod
    def _team_font(w: int, row_h: int, abbr_chars: int, score_chars: int, stripe: int) -> BitmapFont:
        for name in TEAM_FONTS:
            f = get_font(name)
            need = stripe + 2 + f.default_advance * (abbr_chars + score_chars) + 3
            if f.line_height <= row_h - 1 and need <= w:
                return f
        return get_font("tom-thumb")

    def _card(self, c: Canvas, g: Game, now: datetime, text: Color, multi: bool) -> None:
        w, h = c.width, c.height
        status_font = get_font("5x8") if h >= 64 else get_font("4x6") if w >= 48 else get_font("tom-thumb")
        status_h = status_font.line_height
        row_h = (h - status_h - 1) // 2
        stripe = 3 if w >= 64 and h >= 64 else 2 if w >= 48 else 1
        show_scores = g.state in ("live", "final")
        abbr_chars = max(len(g.away.abbr), len(g.home.abbr))
        score_chars = max(len(str(t.score)) for t in g.teams()) if show_scores else 0
        font = self._team_font(w, row_h, abbr_chars, max(2, score_chars), stripe)
        leader = self._leader(g)
        # Wide cards have room for "Twins" instead of "MIN".
        score_w = font.default_advance * max(2, score_chars) + 4 if show_scores else 0
        use_names = all(font.measure(t.name) <= w - stripe - 2 - score_w - 2 for t in g.teams())
        for i, team in enumerate(g.teams()):
            y = i * row_h
            band, ink, bar = self._row_colors(g, team, leader, text)
            if self.settings.team_backgrounds:
                c.rect(0, y, w, row_h - 1, fill=band)
            c.rect(0, y, stripe, row_h - 1, fill=bar)
            ty = y + (row_h - 1 - font.line_height) // 2 + (1 if font.line_height % 2 == 0 else 0)
            c.text(stripe + 2, ty, team.name if use_names else team.abbr, font, ink)
            if show_scores and team.score is not None:
                score = str(team.score)
                c.text(w - font.measure(score) - 2, ty, score, font, ink)
        sy = h - status_h
        if g.state == "live" and g.inning is not None:
            self._baseball_status(c, g, sy, status_font, text)
            return
        if g.state == "pre":
            label = self._start_text(g, w >= 48)
            if multi and w >= 48:
                label = f"{g.league.upper()} {label}"
            color = dim(text, 0.8)
        else:
            label = g.status or g.state.upper()
            color = (255, 90, 80) if g.state == "live" else dim(text, 0.7)
        fonts = [status_font, get_font("tom-thumb")] if status_font.name != "tom-thumb" else [status_font]
        font_s, label = fit_text(label, fonts, w)
        c.text_centered(sy + (status_h - font_s.line_height), label, font_s, color)

    def _row_colors(self, g: Game, team: Team, leader: Team | None, text: Color) -> tuple[Color, Color, Color]:
        """(band, text, bar) for a team's row, straight from its palette.

        The loser of a final keeps its colors at a third of their brightness with grey text, so the
        row reads as greyed out rather than recolored. Without team backgrounds the row is black:
        the name takes the module's text color and the bar the band color (or the accent, when the
        band is black and would vanish).
        """
        pal = palette_for(g.league, team)
        lost = g.state == "final" and leader is not None and leader is not team
        if self.settings.team_backgrounds:
            band, ink, bar = pal.home, pal.text, pal.accent
        else:
            band, ink = (0, 0, 0), text
            bar = pal.accent if max(pal.home) < BLACKISH else pal.home
        if lost:
            band = dim(band, LOSER_DIM)
            return band, LOSER_TEXT_ON_LIGHT if luminance(band) >= 0.3 else LOSER_TEXT, dim(bar, LOSER_DIM)
        return band, ink, bar

    @staticmethod
    def _leader(g: Game) -> Team | None:
        a, b = g.away.score, g.home.score
        if a is None or b is None or a == b:
            return None
        return g.away if a > b else g.home

    def _start_text(self, g: Game, roomy: bool) -> str:
        local = g.start.astimezone(self.ctx.location.tz)
        if self.settings.time_format == "24h":
            return f"{local.hour}:{local.minute:02d}"
        suffix = (" AM" if local.hour < 12 else " PM") if roomy else ("a" if local.hour < 12 else "p")
        return f"{local.hour % 12 or 12}:{local.minute:02d}{suffix}"

    @staticmethod
    def _baseball_status(c: Canvas, g: Game, y: int, font: BitmapFont, text: Color) -> None:
        """Inning on the left (a triangle for top or bottom); bases and outs on the right."""
        h = font.line_height
        mid = y + h // 2
        live = (255, 90, 80)
        # Inning arrow: 5x3, pointing up for the top half, down for the bottom.
        for k in range(3):
            row = mid + 1 - k if g.top else mid - 1 + k
            c.hline(1 + k, row, 5 - 2 * k, live)
        c.text(7, y + (h - font.line_height), str(g.inning), font, live)
        if g.outs is None or g.bases is None:
            return  # between halves: no count to show
        dim_c = dim(text, 0.25)
        # Outs: three 2x2 dots at the right edge.
        ox = c.width - 9
        for k in range(3):
            c.rect(ox + k * 3, mid - 1, 2, 2, fill=OUT_ON if k < g.outs else dim_c)
        # Bases: a diamond of 2x2 squares, second base on top.
        bx = ox - 11
        first, second, third = g.bases
        for x, yy, on in ((bx + 6, mid, first), (bx + 3, mid - 2, second), (bx, mid, third)):
            c.rect(x, yy, 2, 2, fill=BASE_ON if on else dim_c)
