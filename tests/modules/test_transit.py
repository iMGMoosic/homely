from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from homely.core.module import FrameInfo
from homely.modules.transit.module import TransitModule, badge_text, build_rows, upcoming, when_text
from homely.modules.transit.providers import Departure, MetroTransitProvider, StopBoard, TransitError
from homely.modules.transit.providers.metro_transit import parse_departures
from homely.modules.transit.settings import TransitSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import make_ctx
from tests.golden_util import assert_golden

FIXTURES = Path(__file__).parent.parent / "fixtures" / "transit"
CHI = ZoneInfo("America/Chicago")
NOW = datetime(2026, 9, 25, 17, 30, 10, tzinfo=CHI)


def test_parse_nextrip_fixtures():
    board = parse_departures(json.loads((FIXTURES / "nextrip_stop_56334.json").read_text()), 56334)
    assert board.stop_name == "Target Field Station Platform 2"
    assert {d.route for d in board.departures} == {"Blue", "Green"}
    assert all(d.time.tzinfo is not None for d in board.departures)
    assert board.departures == sorted(board.departures, key=lambda d: d.time)
    bus = parse_departures(json.loads((FIXTURES / "nextrip_route2_15UN.json").read_text()), 16137)
    first = bus.departures[0]
    assert (first.route, first.destination, first.direction, first.realtime) == ("2", "Hennepin/Franklin", "WB", True)
    assert not bus.departures[-1].realtime
    assert StopBoard.from_dict(board.to_dict()) == board


@pytest.mark.asyncio
async def test_provider_reports_bad_stop_as_transit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"status": 400, "detail": "Invalid Stop ID"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TransitError, match="Invalid Stop ID"):
            await MetroTransitProvider(client).departures(99999999)


def dep(route: str, minutes: float, realtime: bool = True, dest: str = "Somewhere", direction: str = "SB") -> Departure:
    return Departure(route, route, dest, direction, NOW + timedelta(minutes=minutes, seconds=20), realtime)


BOARD = StopBoard(
    56334,
    "Target Field Station Platform 2",
    [
        dep("Blue", 0.5, dest="Mall of America"),
        dep("2", 4, dest="Hennepin/Franklin", direction="WB"),
        dep("Green", 7, False, dest="Downtown St Paul", direction="EB"),
        dep("Blue", 12, dest="Mall of America"),
        dep("2", 16, dest="Hennepin/Franklin", direction="WB"),
        dep("A", 18, dest="Rosedale", direction="NB"),
        dep("Green", 22, False, dest="Downtown St Paul", direction="EB"),
        dep("Blue", 27, False, dest="Mall of America"),
        dep("2", 31, False, dest="Hennepin/Franklin", direction="WB"),
        dep("Green", 150, False, dest="Downtown St Paul", direction="EB"),
    ],
    ["Both elevators at Franklin Ave Station unavailable until further notice"],
)


def test_filters_walk_time_lookahead_and_routes():
    s = TransitSettings(stop_id=56334)
    assert len(upcoming(BOARD, s, NOW)) == 9  # the 150-minute train is past the 90-minute look-ahead
    walk = upcoming(BOARD, TransitSettings(stop_id=56334, walk_minutes=5), NOW)
    assert walk[0].route == "Green"  # the Blue due now and the 2 in 4 minutes are out of reach
    only = upcoming(BOARD, TransitSettings(stop_id=56334, routes=["blue", "A"]), NOW)
    assert {d.route for d in only} == {"Blue", "A"}


def test_rows_group_by_route_and_direction_soonest_first():
    rows = build_rows(upcoming(BOARD, TransitSettings(stop_id=1), NOW), group=True)
    assert [r.route for r in rows] == ["Blue", "2", "Green", "A"]
    assert len(rows[0].times) == 3
    flat = build_rows(upcoming(BOARD, TransitSettings(stop_id=1), NOW), group=False)
    assert len(flat) == 9 and flat[0].route == "Blue"


def test_when_text():
    assert when_text(dep("2", 0.2), NOW, "12h", CHI) == "Due"
    assert when_text(dep("2", 9), NOW, "12h", CHI) == "9m"
    assert when_text(dep("2", 9, realtime=False), NOW, "12h", CHI) == "5:39"
    assert when_text(dep("2", 9, realtime=False), NOW, "24h", CHI) == "17:39"
    assert badge_text("Green") == "GRN" and badge_text("2") == "2"


def make(size: Size, **kw) -> TransitModule:
    mod = TransitModule(make_ctx(size, now=NOW), TransitSettings(stop_id=56334, **kw))
    mod.board.set(BOARD, NOW)
    mod.on_enter()
    return mod


def render(mod: TransitModule, size: Size, elapsed: float = 0.0):
    canvas = Canvas(size)
    mod.render(canvas, FrameInfo(now=NOW, monotonic=0, dt=0, index=0, slot_elapsed=elapsed, slot_duration=15))
    return canvas.snapshot()


def test_display_rules_and_status_cards():
    mod = TransitModule(make_ctx(Size(128, 32), now=NOW), TransitSettings())
    assert mod.should_display() and mod._status_message() == ("No stop", "pick one in settings")
    mod.settings = TransitSettings(stop_id=56334)
    assert not mod.should_display()  # loading: skip rather than flash a card
    mod.board.fail(TransitError("Invalid Stop ID"))
    assert mod._status_message() == ("Stop not found", "check the stop number")
    late = TransitModule(make_ctx(Size(128, 32), now=NOW + timedelta(hours=4)), TransitSettings(stop_id=56334))
    late.board.set(BOARD, NOW)
    assert not late.should_display()  # nothing left to catch tonight: skip the turn


def test_fps_rises_only_when_something_scrolls():
    assert make(Size(128, 32), show_header=False, routes=["A"]).fps() == 1
    assert make(Size(128, 32)).fps() == 30  # the long stop name scrolls


@pytest.mark.parametrize("variant", ["grouped", "flat", "alerts"])
def test_golden_128x32(variant, request):
    size = Size(128, 32)
    mod = make(size, group_by_route=variant != "flat", show_alerts=variant == "alerts")
    assert_golden(render(mod, size), f"transit/128x32/{variant}", request)


@pytest.mark.parametrize("size", [s for s in SUPPORTED_SIZES if s != Size(128, 32)], ids=str)
def test_golden_other_sizes(size, request):
    img = render(make(size), size)
    assert img.size == size.as_tuple()
    assert_golden(img, f"transit/{size}/grouped", request)


@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_status_card_at_every_size(size):
    mod = TransitModule(make_ctx(size, now=NOW), TransitSettings())
    img = render(mod, size)
    assert sum(1 for p in img.getdata() if p != (18, 20, 30)) > 20
