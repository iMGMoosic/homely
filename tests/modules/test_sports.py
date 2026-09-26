from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from homely.core.module import FrameInfo
from homely.modules.sports.module import SportsModule, game_day, grid, order_games
from homely.modules.sports.providers import Game, Team, palette_for
from homely.modules.sports.providers.espn import EspnProvider, parse_scoreboard
from homely.modules.sports.providers.mlb import parse_schedule
from homely.modules.sports.providers.nhl import parse_score
from homely.modules.sports.settings import SportsSettings
from homely.modules.sports.teams import MLB, NBA, NFL, NHL, Palette
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import make_ctx
from tests.golden_util import assert_golden

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sports"
CHI = ZoneInfo("America/Chicago")
NOW = datetime(2026, 9, 25, 20, 5, tzinfo=CHI)


def test_parse_mlb_schedule():
    games = parse_schedule(json.loads((FIXTURES / "mlb_schedule_2026-09-24.json").read_text()))
    assert len(games) == 12 and all(g.state == "final" and g.league == "mlb" for g in games)
    stl = games[0]
    assert (stl.away.abbr, stl.away.score, stl.home.abbr, stl.home.score) == ("STL", 1, "PIT", 2)
    assert stl.home.name == "Pirates" and stl.home.abbr in MLB
    assert Game.from_dict(stl.to_dict()) == stl


def test_parse_mlb_live_linescore():
    data = {
        "dates": [
            {
                "games": [
                    {
                        "gamePk": 1,
                        "gameDate": "2026-09-26T00:10:00Z",
                        "status": {"abstractGameState": "Live", "detailedState": "In Progress"},
                        "teams": {
                            "away": {"team": {"abbreviation": "DET", "teamName": "Tigers"}, "score": 3},
                            "home": {"team": {"abbreviation": "MIN", "teamName": "Twins"}, "score": 5},
                        },
                        "linescore": {
                            "currentInning": 7,
                            "inningState": "Bottom",
                            "outs": 2,
                            "offense": {"first": {"id": 1}, "third": {"id": 2}},
                        },
                    }
                ]
            }
        ]
    }
    (g,) = parse_schedule(data)
    assert (g.state, g.inning, g.top, g.outs, g.bases) == ("live", 7, False, 2, (True, False, True))
    data["dates"][0]["games"][0]["linescore"]["inningState"] = "Middle"
    (g,) = parse_schedule(data)
    assert g.top is True and g.outs is None and g.bases is None  # the break before the bottom half


def test_parse_nhl_score():
    games = parse_score(json.loads((FIXTURES / "nhl_score_2026-03-10.json").read_text()))
    lak = games[0]
    assert (lak.away.abbr, lak.home.abbr, lak.state, lak.status) == ("LAK", "BOS", "final", "FINAL/OT")
    assert lak.away.name == "Kings"
    assert all(g.away.abbr in NHL and g.home.abbr in NHL for g in games)


def test_parse_espn_scoreboard():
    games = parse_scoreboard(json.loads((FIXTURES / "espn_nfl_scoreboard.json").read_text()), "nfl", "football")
    first = games[0]
    assert (first.away.abbr, first.away.score, first.home.abbr, first.home.score) == ("ATL", 35, "GB", 14)
    assert first.state == "final" and first.home.color == "204e32"
    assert any(g.state == "pre" for g in games)


@pytest.mark.asyncio
async def test_espn_falls_back_to_second_host():
    hosts: list[str] = []
    body = (FIXTURES / "espn_nfl_scoreboard.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(403) if request.url.host == "site.api.espn.com" else httpx.Response(200, content=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        games = await EspnProvider(client, "nfl", "football", "nfl").games(NOW.date())
    assert games and hosts == ["site.api.espn.com", "site.web.api.espn.com"]


def test_palettes_cover_every_team_each_feed_names():
    mlb = parse_schedule(json.loads((FIXTURES / "mlb_schedule_2026-09-24.json").read_text()))
    nhl = parse_score(json.loads((FIXTURES / "nhl_score_2026-03-10.json").read_text()))
    nfl = parse_scoreboard(json.loads((FIXTURES / "espn_nfl_scoreboard.json").read_text()), "nfl", "football")
    for table, games in ((MLB, mlb), (NHL, nhl), (NFL, nfl)):
        assert {t.abbr for g in games for t in g.teams()} <= set(table)
    assert (len(MLB), len(NFL), len(NBA), len(NHL)) == (30, 32, 30, 32)


def test_palette_used_as_written_with_espn_fallback():
    twins = palette_for("mlb", Team("MIN", "Twins", 5))
    assert twins == Palette((12, 35, 64), (255, 255, 255), (186, 12, 47))
    assert palette_for("nhl", Team("MIN", "Wild", 2)) == NHL["MIN"]
    assert palette_for("nfl", Team("PIT", "Steelers", 7)).text == (0, 0, 0)  # black on gold, as listed
    lynx = palette_for("wnba", Team("MIN", "Lynx", 80, "266092", "79bc43"))
    assert lynx == Palette((0x26, 0x60, 0x92), (255, 255, 255), (0x79, 0xBC, 0x43))
    light = palette_for("mls", Team("X", "X", 0, "f5f5f5", ""))
    assert light.text == (0, 0, 0) and light.accent == light.home


def test_background_styles_and_old_bool_setting():
    assert SportsSettings(team_backgrounds=True).team_backgrounds == "translucent"
    assert SportsSettings(team_backgrounds=False).team_backgrounds == "off"
    game = Game("nfl", "9", NOW, "final", Team("PIT", "Steelers", 7), Team("GB", "Packers", 21), "FINAL")
    solid = SportsModule(make_ctx(Size(64, 32), now=NOW), SportsSettings(team_backgrounds="solid"))
    assert solid._row_colors(game, game.away, (255, 255, 255)) == ((255, 182, 18), (0, 0, 0), (0, 0, 0))
    tinted = SportsModule(make_ctx(Size(64, 32), now=NOW), SportsSettings())
    # Translucent is the band at 30%; text and bar stay exactly as listed, even black on gold.
    assert tinted._row_colors(game, game.away, (255, 255, 255)) == ((76, 55, 5), (0, 0, 0), (0, 0, 0))
    assert tinted._row_colors(game, game.home, (255, 255, 255))[1:] == (NFL["GB"].text, NFL["GB"].accent)
    off = SportsModule(make_ctx(Size(64, 32), now=NOW), SportsSettings(team_backgrounds="off"))
    assert off._row_colors(game, game.away, (1, 2, 3))[:2] == (None, (1, 2, 3))


def t(abbr: str, name: str, score: int | None, colors: tuple[str, str] = ("", "")) -> Team:
    return Team(abbr, name, score, *colors)


GAMES = [
    Game(
        "mlb", "1", NOW - timedelta(hours=1), "live",
        t("DET", "Tigers", 3), t("MIN", "Twins", 5),
        inning=7, top=True, outs=2, bases=(True, False, True),
    ),
    Game("nhl", "2", NOW - timedelta(minutes=40), "live", t("CHI", "Blackhawks", 1),
         t("MIN", "Wild", 2), "P2 12:01"),
    Game("nfl", "3", NOW - timedelta(hours=3), "final", t("ATL", "Falcons", 35, ("a71930", "000000")),
         t("GB", "Packers", 14, ("204e32", "ffb612")), "FINAL"),
    Game("wnba", "4", NOW + timedelta(hours=1), "pre", t("NY", "Liberty", None, ("86cebc", "000000")),
         t("MIN", "Lynx", None, ("266092", "79bc43"))),
    Game("mlb", "5", NOW - timedelta(hours=2), "final", t("NYY", "Yankees", 6),
         t("TB", "Rays", 4), "F/10"),
    Game("mlb", "6", NOW + timedelta(hours=2), "off", t("SEA", "Mariners", None),
         t("HOU", "Astros", None), "PPD"),
]  # fmt: skip


def test_order_favorites_first_then_live_upcoming_final():
    s = SportsSettings(favorites=["MIN"], wnba=True)
    order = [(g.id, fav) for g, fav in order_games(GAMES, s)]
    assert order == [("1", True), ("2", True), ("4", True), ("3", False), ("5", False)]  # PPD not a favorite
    only = SportsSettings(favorites=["nhl:MIN"], show="favorites_only")
    assert [g.id for g, _ in order_games(GAMES, only)] == ["2"]
    by_name = SportsSettings(favorites=["packers"], show="favorites_only", show_finals=True)
    assert [g.id for g, _ in order_games(GAMES, by_name)] == ["3"]
    no_finals = SportsSettings(show="all", show_finals=False, show_upcoming=False, wnba=True)
    assert [g.id for g, _ in order_games(GAMES, no_finals)] == ["1", "2"]  # by start time


def test_game_day_rolls_over_at_5am():
    assert game_day(datetime(2026, 9, 26, 1, 30, tzinfo=CHI), CHI).isoformat() == "2026-09-25"
    assert game_day(datetime(2026, 9, 26, 6, 0, tzinfo=CHI), CHI).isoformat() == "2026-09-26"


def test_grid_fills_the_panel():
    assert grid(Size(128, 32)) == (2, 1)
    assert grid(Size(64, 64)) == (1, 2)
    assert grid(Size(32, 32)) == (1, 1)
    assert grid(Size(128, 128)) == (2, 2)


@pytest.mark.asyncio
async def test_fetch_throttles_quiet_leagues_and_keeps_going_when_one_fails(tmp_path):
    calls: list[str] = []
    mlb_body = (FIXTURES / "mlb_schedule_2026-09-24.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if "mlb" in request.url.host:
            return httpx.Response(200, content=mlb_body)
        return httpx.Response(500)

    clock = {"now": NOW}
    ctx = make_ctx(Size(128, 32), now=NOW, tmp=tmp_path)
    ctx._now = lambda tz=None: clock["now"].astimezone(tz) if tz else clock["now"]
    ctx._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    mod = SportsModule(ctx, SportsSettings(nfl=False, nba=False, nhl=True))
    await mod._fetch()
    assert mod.games.value and all(g.league == "mlb" for g in mod.games.value)
    assert calls.count("statsapi.mlb.com") == 1 and calls.count("api-web.nhle.com") == 1
    clock["now"] = NOW + timedelta(seconds=30)
    await mod._fetch()  # every MLB game is final: not due again for ten minutes; NHL failed, so retried
    assert calls.count("statsapi.mlb.com") == 1 and calls.count("api-web.nhle.com") == 2
    clock["now"] = NOW + timedelta(minutes=11)
    await mod._fetch()
    assert calls.count("statsapi.mlb.com") == 2


def make(size: Size, games: list[Game] = GAMES, **kw) -> SportsModule:
    settings = SportsSettings(**{"favorites": ["MIN"], "wnba": True, **kw})
    mod = SportsModule(make_ctx(size, now=NOW), settings)
    mod.games.set(list(games), NOW)
    mod.on_enter()
    return mod


def render(mod: SportsModule, size: Size, elapsed: float = 0.0):
    canvas = Canvas(size)
    frame = FrameInfo(now=NOW, monotonic=0, dt=0, index=0, slot_elapsed=elapsed, slot_duration=mod.duration())
    mod.render(canvas, frame)
    return canvas.snapshot()


def test_turn_length_follows_pages_and_rotates_other_games():
    mod = make(Size(128, 32), max_games=3, seconds_per_page=5)
    assert [g.id for g, _ in mod._turn] == ["1", "2", "4"] and mod.duration() == 10.0
    mod = make(Size(128, 32), max_games=4)
    first = [g.id for g, _ in mod._turn]
    mod.on_enter()
    assert first == ["1", "2", "4", "3"] and [g.id for g, _ in mod._turn] == ["1", "2", "4", "5"]


def test_status_when_nothing_to_show():
    mod = SportsModule(make_ctx(Size(64, 32), now=NOW), SportsSettings(mlb=False, nfl=False, nba=False, nhl=False))
    assert mod.should_display() and mod._status_message() == ("No leagues", "pick some in settings")
    quiet = make(Size(64, 32), favorites=["SEA"], show="favorites_only", games=GAMES[:5])
    assert not quiet.should_display()


@pytest.mark.parametrize("page", [0, 1, 2])
def test_golden_128x32(page, request):
    size = Size(128, 32)
    assert_golden(render(make(size), size, elapsed=page * 6 + 1), f"sports/128x32/page{page}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(128, 32)], ids=str)
def test_golden_other_sizes(size, request):
    img = render(make(size), size)
    assert img.size == size.as_tuple()
    assert_golden(img, f"sports/{size}/first", request)


def test_golden_single_game_fills_wide_panel(request):
    size = Size(128, 32)
    mod = make(size, favorites=["nhl:MIN"], show="favorites_only")
    assert_golden(render(mod, size), "sports/128x32/single", request)
