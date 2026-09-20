"""The module (applet) API. Everything a contributor implements lives here."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

from homely.render.canvas import Canvas
from homely.render.layout import resolve
from homely.render.size import Orientation, Size

if TYPE_CHECKING:
    import httpx

    from homely.core.input import InputEvent
    from homely.data.location import LocationService
    from homely.data.poller import Poller


class Tier(str, Enum):
    NEED = "need"
    WANT = "want"
    COOL = "cool"


class ModuleSettings(BaseModel):
    """Base for per-module settings.

    Declare fields with ``Field(title=..., description=..., json_schema_extra={...})``.
    Recognised UI hints in json_schema_extra: ``x-widget`` (color, slider, textarea,
    string-list, location, time, timezone, hidden), ``x-group``, ``x-order``, ``x-unit``,
    ``x-placeholder``, ``x-help``.
    """

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ModuleInfo:
    id: str
    name: str
    description: str
    tier: Tier
    icon: str | None = None
    version: str = "0.1.0"
    author: str = ""
    supports_portrait: bool = True
    min_size: Size = Size(32, 32)
    default_duration_s: float = 15.0
    default_fps: int = 0
    accepts_input: bool = False
    can_overlay: bool = False
    allow_multiple: bool = False
    upscale_ok: bool = True  # allow integer upscaling of a smaller exact layout on big panels


@dataclass(frozen=True)
class FrameInfo:
    now: datetime
    monotonic: float
    dt: float
    index: int
    slot_elapsed: float
    slot_duration: float

    @property
    def progress(self) -> float:
        if self.slot_duration <= 0 or self.slot_duration == float("inf"):
            return 0.0
        return max(0.0, min(1.0, self.slot_elapsed / self.slot_duration))


class Clock(Protocol):
    def __call__(self, tz: tzinfo | None = None) -> datetime: ...


PollFn = Callable[[], Awaitable[Any]]


class ModuleContext:
    """Everything a module may touch. Built by the registry per instance."""

    def __init__(
        self,
        *,
        instance_id: str,
        size: Size,
        orientation: Orientation,
        location: LocationService,
        http: httpx.AsyncClient | None,
        log: logging.Logger,
        data_dir: Path,
        now: Clock,
        make_poller: Callable[[str, timedelta, PollFn, float, bool], Poller],
        invalidate: Callable[[], None],
        request_takeover: Callable[[int, float | None], None],
        release_takeover: Callable[[], None],
    ) -> None:
        self.instance_id = instance_id
        self.size = size
        self.orientation = orientation
        self.location = location
        self._http = http
        self.log = log
        self.data_dir = data_dir
        self._now = now
        self._make_poller = make_poller
        self._invalidate = invalidate
        self._request_takeover = request_takeover
        self._release_takeover = release_takeover
        self.pollers: list[Poller] = []
        from homely.data.diskcache import DiskCache

        self.cache = DiskCache(data_dir)

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("HTTP client not available in this context")
        return self._http

    def now(self, tz: tzinfo | None = None) -> datetime:
        return self._now(tz)

    def poll(
        self,
        name: str,
        every: timedelta,
        fn: PollFn,
        *,
        jitter: float = 0.1,
        run_immediately: bool = True,
    ) -> Poller:
        poller = self._make_poller(name, every, fn, jitter, run_immediately)
        self.pollers.append(poller)
        return poller

    def invalidate(self) -> None:
        """Ask the scheduler to re-render this module (static modules only need this)."""
        self._invalidate()

    def request_takeover(self, *, priority: int = 10, timeout: float | None = None) -> None:
        self._request_takeover(priority, timeout)

    def release_takeover(self) -> None:
        self._release_takeover()


S = TypeVar("S", bound=ModuleSettings)


class Module(Generic[S]):
    """Base class for all modules. Subclass, set ``info`` and ``Settings``, add @layout methods."""

    info: ClassVar[ModuleInfo]
    Settings: ClassVar[type[ModuleSettings]] = ModuleSettings

    def __init__(self, ctx: ModuleContext, settings: S) -> None:
        self.ctx = ctx
        self.settings: S = settings

    # ---- lifecycle (asyncio thread) ---------------------------------------------

    async def setup(self) -> None:
        """Register pollers, load assets. Pollers are cancelled automatically on teardown."""

    async def teardown(self) -> None:
        pass

    async def on_settings_changed(self, settings: S) -> None:
        self.settings = settings

    # ---- scheduling (render thread; must be fast) -------------------------------

    def should_display(self) -> bool:
        return True

    def duration(self) -> float:
        return self.info.default_duration_s

    def fps(self) -> int:
        return self.info.default_fps

    def on_enter(self) -> None:
        """Called each time the rotation flips to this module, before its first frame.

        An animation restarts here rather than resuming where its last turn left off: on a
        panel showing a dozen modules, picking up a half-finished maze or a light-cycle round
        that ended while the module was off screen just looks broken. Modules whose whole
        output comes from the clock or from polled data have nothing to restart and can leave
        this alone. Make sure ``info.default_duration_s`` is long enough for one full round.
        """

    def on_exit(self) -> None:
        pass

    # ---- rendering (render thread) ----------------------------------------------

    def render(self, canvas: Canvas, frame: FrameInfo) -> None:
        """Dispatch to the best @layout for this canvas size.

        When a smaller exact layout is reused on a bigger panel it is integer-upscaled
        (if ``info.upscale_ok`` and the factor is >= 2) or centered.
        """
        res = resolve(type(self), canvas.size)
        designed = res.designed_for
        if designed is None or designed == canvas.size:
            res.renderer(self, canvas, frame)
            return
        factor = min(canvas.width // designed.w, canvas.height // designed.h)
        if self.info.upscale_ok and factor >= 2:
            small = Canvas(designed)
            res.renderer(self, small, frame)
            img = small.upscaled(factor)
            canvas.blit(img, (canvas.width - img.width) // 2, (canvas.height - img.height) // 2)
        else:
            sub = canvas.sub(
                (canvas.width - designed.w) // 2, (canvas.height - designed.h) // 2, designed.w, designed.h
            )
            res.renderer(self, sub, frame)

    # ---- input (render thread; only while holding a takeover) -------------------

    def handle_input(self, event: InputEvent) -> None:
        pass
