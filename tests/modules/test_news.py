from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from homely.core.module import FrameInfo
from homely.modules.news.feeds import FeedFetcher, Headline, clean_title, parse_feed
from homely.modules.news.module import NewsModule, age_text, order_headlines
from homely.modules.news.settings import FeedSource, NewsSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_rss_fixtures():
    title, items = parse_feed((FIXTURES / "rss_bbc_world.xml").read_bytes(), source_name="", color="#BB1919")
    assert "BBC" in title and len(items) > 10
    assert items[0].source == title and items[0].published is not None and items[0].published.tzinfo is not None
    _, hn = parse_feed((FIXTURES / "rss_hn.xml").read_bytes(), source_name="HN", color="#FF6600")
    assert hn and hn[0].source == "HN" and hn[0].link.startswith("http")
    assert clean_title("  Hello &amp; <b>world</b>\n now ") == "Hello & world now"
    again = Headline.from_dict(items[0].to_dict())
    assert again == items[0]


def test_order_interleave_and_newest():
    t0 = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

    def h(src: str, minutes: int) -> Headline:
        return Headline(f"{src}{minutes}", "", t0 - timedelta(minutes=minutes), src, "#fff")

    per = {"a": [h("a", 30), h("a", 5)], "b": [h("b", 10), h("b", 50), h("b", 60)]}
    inter = [x.title for x in order_headlines(per, "interleave")]
    assert inter == ["a5", "b10", "a30", "b50", "b60"]
    newest = [x.title for x in order_headlines(per, "newest")]
    assert newest == ["a5", "b10", "a30", "b50", "b60"]
    assert age_text(t0 - timedelta(minutes=3), t0) == "3m"
    assert age_text(t0 - timedelta(hours=5), t0) == "5h"
    assert age_text(t0 - timedelta(days=2), t0) == "2d"
    assert age_text(None, t0) == ""


@pytest.mark.asyncio
async def test_fetcher_conditional_requests():
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.headers))
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=(FIXTURES / "rss_hn.xml").read_bytes(), headers={"ETag": '"v1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        f = FeedFetcher(client)
        first = await f.fetch_and_parse("https://example/feed", source_name="", color="#fff")
        assert first is not None and first[1]
        assert await f.fetch_and_parse("https://example/feed", source_name="", color="#fff") is None
    assert "if-none-match" not in calls[0] and calls[1]["if-none-match"] == '"v1"'


@pytest.mark.asyncio
async def test_fetch_tolerates_one_bad_feed(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if "bad" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, content=(FIXTURES / "rss_bbc_world.xml").read_bytes())

    ctx = make_ctx(Size(64, 64), now=FROZEN, tmp=tmp_path)
    ctx._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = NewsSettings(
        feeds=[
            FeedSource(name="Bad", url="https://bad.example/rss"),
            FeedSource(name="BBC", url="https://ok.example/rss"),
        ],
        max_age_hours=168,
    )
    mod = NewsModule(ctx, settings)
    await mod.setup()
    await mod._fetch()
    assert mod.should_display() and all(h.source == "BBC" for h in mod.headlines.value or [])
    assert ctx.cache.get("headlines") is not None


HEADLINES = [
    Headline(
        "Council approves new light rail extension to the airport",
        "",
        FROZEN - timedelta(minutes=12),
        "Star Tribune",
        "#00A8FF",
    ),
    Headline("Short one", "", FROZEN - timedelta(hours=3), "BBC World", "#BB1919"),
    Headline(
        "Researchers demonstrate a supercalifragilistic battery chemistry that doubles range in cold weather tests",
        "",
        FROZEN - timedelta(days=1, hours=2),
        "Hacker News",
        "#FF6600",
    ),
]


def make(settings: NewsSettings, size: Size) -> NewsModule:
    ctx = make_ctx(size, now=FROZEN)
    mod = NewsModule(ctx, settings)
    mod.headlines.set(list(HEADLINES), FROZEN)
    mod.on_enter()
    return mod


def render(mod: NewsModule, size: Size, elapsed: float, dt: float = 1.0):
    canvas = Canvas(size)
    frame = FrameInfo(now=FROZEN, monotonic=100.0, dt=dt, index=0, slot_elapsed=elapsed, slot_duration=21)
    mod.render(canvas, frame)
    return canvas.snapshot()


def test_rotation_cursor_and_duration():
    mod = make(NewsSettings(headlines_per_slot=2, seconds_per_headline=5), Size(64, 64))
    assert [h.title for h in mod._current] == [HEADLINES[0].title, HEADLINES[1].title]
    assert mod.duration() == 10 and mod.fps() == 1
    mod.on_enter()  # next turn continues where it left off, wrapping around
    assert [h.title for h in mod._current] == [HEADLINES[2].title, HEADLINES[0].title]
    assert mod._marquee_mode(Size(32, 32)) and not mod._marquee_mode(Size(64, 32))
    assert not mod._marquee_mode(Size(32, 64))


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_golden_64x64(idx, request):
    mod = make(NewsSettings(), Size(64, 64))
    assert_golden(render(mod, Size(64, 64), elapsed=idx * 7 + 1), f"news/64x64/headline_{idx}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(64, 64)], ids=str)
def test_golden_other_sizes(size, request):
    mod = make(NewsSettings(), size)
    img = render(mod, size, elapsed=1, dt=0.0)
    assert img.size == size.as_tuple()
    assert_golden(img, f"news/{size}/headline_0", request)
