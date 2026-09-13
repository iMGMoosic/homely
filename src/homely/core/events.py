"""A tiny typed pub/sub bus bridging the render thread and the asyncio main thread."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigChanged:
    scope: Literal["panel", "display", "web", "location", "rotation", "brightness", "modules", "all"]
    instance_id: str | None = None


@dataclass(frozen=True)
class ModuleChanged:
    instance_id: str | None
    phase: str


@dataclass(frozen=True)
class ModuleError:
    instance_id: str
    message: str


@dataclass(frozen=True)
class BrightnessChanged:
    level: int


@dataclass(frozen=True)
class TakeoverChanged:
    instance_id: str | None


@dataclass(frozen=True)
class LogLine:
    level: str
    logger: str
    message: str
    ts: float


@dataclass(frozen=True)
class RestartRequested:
    reason: str


Event = Any
Callback = Callable[[Event], None]


@dataclass
class _Subscription:
    types: tuple[type, ...]
    callback: Callback | None = None
    aqueue: asyncio.Queue[Event] | None = None
    tqueue: queue.Queue[Event] | None = None
    loop: asyncio.AbstractEventLoop | None = None
    _extra: dict[str, Any] = field(default_factory=dict)

    def matches(self, event: Event) -> bool:
        return not self.types or isinstance(event, self.types)


class EventBus:
    """publish() may be called from any thread. Subscribers choose their delivery style."""

    def __init__(self) -> None:
        self._subs: list[_Subscription] = []
        self._lock = threading.Lock()

    def publish(self, event: Event) -> None:
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            if not sub.matches(event):
                continue
            try:
                if sub.callback is not None:
                    sub.callback(event)
                elif sub.tqueue is not None:
                    sub.tqueue.put_nowait(event)
                elif sub.aqueue is not None and sub.loop is not None:
                    sub.loop.call_soon_threadsafe(_put_dropping, sub.aqueue, event)
            except Exception:
                log.exception("event subscriber failed for %r", event)

    def subscribe(self, callback: Callback, *types: type) -> Callable[[], None]:
        """Synchronous callback, invoked on the publishing thread."""
        sub = _Subscription(types=types, callback=callback)
        return self._add(sub)

    def subscribe_threadsafe(self, *types: type) -> tuple[queue.Queue[Event], Callable[[], None]]:
        """A thread-safe queue the render thread can drain between frames."""
        q: queue.Queue[Event] = queue.Queue()
        sub = _Subscription(types=types, tqueue=q)
        return q, self._add(sub)

    def subscribe_async(
        self, *types: type, loop: asyncio.AbstractEventLoop | None = None, maxsize: int = 256
    ) -> tuple[asyncio.Queue[Event], Callable[[], None]]:
        """An asyncio queue fed via call_soon_threadsafe; must be created inside a running loop."""
        loop = loop or asyncio.get_running_loop()
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        sub = _Subscription(types=types, aqueue=q, loop=loop)
        return q, self._add(sub)

    def _add(self, sub: _Subscription) -> Callable[[], None]:
        with self._lock:
            self._subs.append(sub)

        def unsubscribe() -> None:
            with self._lock:
                if sub in self._subs:
                    self._subs.remove(sub)

        return unsubscribe


def _put_dropping(q: asyncio.Queue[Event], event: Event) -> None:
    if q.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            q.get_nowait()
    q.put_nowait(event)
