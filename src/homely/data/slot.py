"""DataSlot: a thread-safe holder for the latest fetched value of something."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Generic, TypeVar

T = TypeVar("T")


class DataSlot(Generic[T]):
    """Written by an asyncio poller, read by the render thread.

    Reads of ``value`` are atomic reference reads; the lock protects compound updates.
    """

    def __init__(self, value: T | None = None) -> None:
        self._lock = threading.Lock()
        self.value: T | None = value
        self.fetched_at: datetime | None = None
        self.error: Exception | None = None
        self.error_count: int = 0

    def set(self, value: T, now: datetime) -> None:
        with self._lock:
            self.value = value
            self.fetched_at = now
            self.error = None
            self.error_count = 0

    def fail(self, exc: Exception) -> None:
        with self._lock:
            self.error = exc
            self.error_count += 1

    def clear(self) -> None:
        with self._lock:
            self.value = None
            self.fetched_at = None
            self.error = None
            self.error_count = 0

    @property
    def has_value(self) -> bool:
        return self.value is not None

    def age(self, now: datetime) -> timedelta | None:
        if self.fetched_at is None:
            return None
        return now - self.fetched_at

    def is_stale(self, now: datetime, ttl: timedelta) -> bool:
        """True when there is a value but it is older than ttl (or a fetch has since failed)."""
        if self.fetched_at is None:
            return False
        return (now - self.fetched_at) > ttl
