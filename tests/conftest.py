from __future__ import annotations

import logging
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homely.core.module import ModuleContext
from homely.data.location import LocationConfig, LocationService
from homely.render.size import Orientation, Size

FROZEN = datetime(2026, 9, 12, 13, 37, 42, tzinfo=ZoneInfo("America/Chicago"))


class FakeClock:
    """Monotonic clock for driving the scheduler deterministically."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> float:
        self.t += dt
        return self.t


@pytest.fixture
def frozen_now() -> datetime:
    return FROZEN


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


def make_ctx(size: Size = Size(64, 64), now: datetime = FROZEN, tmp: Path | None = None) -> ModuleContext:
    location = LocationService(LocationConfig(timezone="America/Chicago"))
    recorded: list[tuple[str, timedelta]] = []

    def make_poller(name, every, fn, jitter, run_immediately):
        from homely.data.poller import Poller

        recorded.append((name, every))
        return Poller(name, every, fn, jitter=jitter, run_immediately=run_immediately)

    def _now(tz: tzinfo | None = None) -> datetime:
        return now.astimezone(tz) if tz else now

    ctx = ModuleContext(
        instance_id="test",
        size=size,
        orientation=Orientation.LANDSCAPE if size.w >= size.h else Orientation.PORTRAIT,
        location=location,
        http=None,
        log=logging.getLogger("test"),
        data_dir=tmp or Path("/tmp/homely-test"),
        now=_now,
        make_poller=make_poller,
        invalidate=lambda: None,
        request_takeover=lambda p, t: None,
        release_takeover=lambda: None,
    )
    return ctx


@pytest.fixture
def ctx64(tmp_path: Path) -> ModuleContext:
    return make_ctx(Size(64, 64), tmp=tmp_path)


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", default=False, help="rewrite golden images")
