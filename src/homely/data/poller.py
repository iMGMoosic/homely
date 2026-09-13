"""Poller: run an async fetch on an interval with jitter and exponential backoff."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

PollFn = Callable[[], Awaitable[object]]


class Poller:
    def __init__(
        self,
        name: str,
        every: timedelta,
        fn: PollFn,
        *,
        jitter: float = 0.1,
        run_immediately: bool = True,
        logger: logging.Logger | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.name = name
        self.every = every
        self.fn = fn
        self.jitter = max(0.0, jitter)
        self.run_immediately = run_immediately
        self.log = logger or log
        self._now = now_fn or (lambda: datetime.now().astimezone())  # noqa: TID251
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self.last_run: datetime | None = None
        self.last_error: Exception | None = None
        self.next_run: datetime | None = None
        self.failures = 0

    # ---- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name=f"poller:{self.name}")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None

    def trigger(self) -> None:
        """Fetch as soon as possible (e.g. after settings changed)."""
        self._wake.set()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # ---- internals -----------------------------------------------------------

    def _delay_after_success(self) -> float:
        base = self.every.total_seconds()
        return base * (1 + random.uniform(-self.jitter, self.jitter))

    def _delay_after_failure(self) -> float:
        base = min(self.every.total_seconds(), 30.0)
        cap = max(self.every.total_seconds(), 1800.0)
        return float(min(cap, base * (2 ** min(self.failures, 10))) * (1 + random.uniform(0, self.jitter)))

    async def run_once(self) -> bool:
        """Run the fetch once; returns True on success. Never raises."""
        self.last_run = self._now()
        try:
            await self.fn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failures += 1
            self.last_error = exc
            self.log.warning("poller %s failed (%d): %s", self.name, self.failures, exc)
            return False
        self.failures = 0
        self.last_error = None
        return True

    async def _run(self) -> None:
        if not self.run_immediately:
            await self._sleep(self._delay_after_success())
        while True:
            ok = await self.run_once()
            delay = self._delay_after_success() if ok else self._delay_after_failure()
            await self._sleep(delay)

    async def _sleep(self, delay: float) -> None:
        self.next_run = self._now() + timedelta(seconds=delay)
        self._wake.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._wake.wait(), timeout=delay)
        self.next_run = None
