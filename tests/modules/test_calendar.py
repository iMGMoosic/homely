from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from pydantic import ValidationError

from homely.core.module import FrameInfo
from homely.modules.calendar.ics import Event, parse_ics
from homely.modules.calendar.module import CalendarModule, clock_text, day_label, paginate, upcoming
from homely.modules.calendar.settings import CalendarSettings, CalendarSource
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden

ICS = (Path(__file__).parent.parent / "fixtures" / "calendar_sample.ics").read_bytes()
CHI = ZoneInfo("America/Chicago")
NOW = FROZEN  # Saturday 2026-09-12 13:37 CDT


def fixture_events() -> list[Event]:
    return parse_ics(ICS, NOW - timedelta(days=1), NOW + timedelta(days=8), CHI, "#4F9DFF")


def test_parse_expands_recurrences_and_skips_cancelled():
    events = fixture_events()
    titles = [e.title for e in events]
    assert "Cancelled lunch" not in titles
    standups = [e for e in events if e.title == "Team standup"]
    days = [e.start.day for e in standups]
    assert 14 not in days and days[:4] == [15, 16, 17, 18]  # Monday the 14th is an EXDATE
    assert standups[0].start.hour == 9 and standups[0].start.minute == 30
    bday = next(e for e in events if e.title == "Grandma's birthday")
    assert bday.all_day and bday.start == datetime(2026, 9, 13, tzinfo=CHI)
    dentist = next(e for e in events if e.title == "Dentist")
    assert dentist.start.astimezone(CHI).hour == 14 and dentist.location == "Uptown Dental"
    assert Event.from_dict(dentist.to_dict()) == dentist


def test_webcal_links_become_https():
    assert CalendarSource(url="webcal://example.com/cal.ics").url == "https://example.com/cal.ics"
    with pytest.raises(ValidationError):
        CalendarSource(url="ftp://example.com/cal.ics")


def test_upcoming_drops_finished_and_optional_all_day():
    events = fixture_events()
    s = CalendarSettings()
    left = upcoming(events, NOW, s)
    assert left[0].title.startswith("Farmers market")  # under way: 12:00-15:00
    later = upcoming(events, NOW.replace(hour=16), s)
    assert not any(e.title.startswith("Farmers") for e in later)
    assert all(not e.all_day for e in upcoming(events, NOW, CalendarSettings(show_all_day=False)))
    assert all(e.start < NOW + timedelta(days=2) for e in upcoming(events, NOW, CalendarSettings(days_ahead=2)))


def test_paginate_packs_days_by_height():
    events = upcoming(fixture_events(), NOW, CalendarSettings())
    # Room for three 8 px rows; each further day on a page costs a 7 px label.
    pages = paginate(events, 25, 8, 7, NOW, CHI)
    assert [[(d.day, len(evs)) for d, evs in p.days] for p in pages[:2]] == [[(12, 1), (13, 1)], [(14, 1), (15, 1)]]
    roomy = paginate(events, 200, 8, 7, NOW, CHI)
    assert len(roomy) == 1 and sum(len(evs) for _, evs in roomy[0].days) == len(events)


def test_labels_and_times():
    today = NOW.date()
    assert day_label(today, today, True) == "Today"
    assert day_label(today + timedelta(days=1), today, True) == "Tomorrow"
    assert day_label(today + timedelta(days=1), today, False) == "Tmrw"
    assert day_label(today + timedelta(days=3), today, True) == "Tue 15"
    assert day_label(today + timedelta(days=30), today, True) == "Mon Oct 12"
    assert day_label(today + timedelta(days=30), today, False) == "Oct 12"
    assert clock_text(NOW.replace(hour=9, minute=0), "12h") == "9a"
    assert clock_text(NOW.replace(hour=17, minute=30), "12h") == "5:30p"
    assert clock_text(NOW.replace(hour=17, minute=30), "24h") == "17:30"


@pytest.mark.asyncio
async def test_fetch_merges_calendars_and_survives_a_broken_one(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, content=ICS, headers={"ETag": '"v1"'})

    ctx = make_ctx(Size(128, 32), now=NOW, tmp=tmp_path)
    ctx._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = CalendarSettings(
        calendars=[
            CalendarSource(url="https://example.com/broken.ics"),
            CalendarSource(url="https://example.com/home.ics", color="#E0508A"),
        ]
    )
    mod = CalendarModule(ctx, settings)
    await mod.setup()
    await mod._fetch()
    assert mod.events.value and all(e.color == "#E0508A" for e in mod.events.value)
    assert mod.should_display()
    assert ctx.cache.get("events") is not None


def test_status_and_empty_rules():
    mod = CalendarModule(make_ctx(Size(64, 32), now=NOW), CalendarSettings())
    assert mod.should_display() and mod._status_message() == ("No calendar", "add an ICS link in settings")
    s = CalendarSettings(calendars=[CalendarSource(url="https://example.com/a.ics")])
    quiet = CalendarModule(make_ctx(Size(64, 32), now=NOW), s)
    assert not quiet.should_display()  # still loading
    quiet.events.set([], NOW)
    assert not quiet.should_display()
    quiet.settings = s.model_copy(update={"show_when_empty": True})
    assert quiet.should_display()


def at(hour: int, minute: int = 0) -> datetime:
    return NOW.replace(hour=hour, minute=minute, second=0)


EXTRA = [
    Event("Pick up CSA box", at(17, 30), at(18), False, "#3FBF6F"),
    Event("Book club", at(19), at(21), False, "#E0508A"),
]


def make(size: Size, **kw) -> CalendarModule:
    settings = CalendarSettings(calendars=[CalendarSource(url="https://example.com/a.ics")], **kw)
    mod = CalendarModule(make_ctx(size, now=NOW), settings)
    mod.events.set(sorted(fixture_events() + EXTRA, key=lambda e: (e.start, not e.all_day)), NOW)
    mod.on_enter()
    return mod


def render(mod: CalendarModule, size: Size, elapsed: float = 0.0):
    canvas = Canvas(size)
    frame = FrameInfo(now=NOW, monotonic=0, dt=0, index=0, slot_elapsed=elapsed, slot_duration=mod.duration())
    mod.render(canvas, frame)
    return canvas.snapshot()


def test_turn_length_and_fps():
    mod = make(Size(128, 32))
    assert mod.duration() == len(mod._turn) * 6
    assert mod.fps() == 30  # the farmers market title is too long for the row and scrolls


@pytest.mark.parametrize("page", [0, 1])
def test_golden_128x32(page, request):
    size = Size(128, 32)
    assert_golden(render(make(size), size, elapsed=page * 6 + 1), f"calendar/128x32/page{page}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(128, 32)], ids=str)
def test_golden_other_sizes(size, request):
    img = render(make(size), size)
    assert img.size == size.as_tuple()
    assert_golden(img, f"calendar/{size}/first", request)


def test_golden_nothing_coming_up(request):
    size = Size(128, 32)
    mod = CalendarModule(
        make_ctx(size, now=NOW),
        CalendarSettings(calendars=[CalendarSource(url="https://example.com/a.ics")], show_when_empty=True),
    )
    mod.events.set([], NOW)
    assert_golden(render(mod, size), "calendar/128x32/empty", request)
