"""InstanceManager: turns config ModuleEntry rows into live Module instances.

Runs on the asyncio thread. Owns setup/teardown, pollers, and pushes the resulting
rotation to the Scheduler (which runs on the render thread).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any

import httpx

from homely.config.models import AppConfig, ModuleEntry
from homely.core.module import ModuleContext
from homely.core.registry import ModuleInstance, ModuleRegistry, parse_settings
from homely.core.scheduler import Scheduler
from homely.data.location import LocationService
from homely.data.poller import Poller
from homely.render.layout import UnsupportedSize, resolve
from homely.render.size import Orientation, Size

log = logging.getLogger(__name__)


class InstanceManager:
    def __init__(
        self,
        registry: ModuleRegistry,
        scheduler: Scheduler,
        *,
        size: Size,
        orientation: Orientation,
        location: LocationService,
        http: httpx.AsyncClient | None,
        data_dir: Path,
        start_pollers: bool = True,
    ) -> None:
        self.registry = registry
        self.scheduler = scheduler
        self.size = size
        self.orientation = orientation
        self.location = location
        self.http = http
        self.data_dir = data_dir
        self.start_pollers = start_pollers
        self.instances: dict[str, ModuleInstance] = {}
        self.unavailable: dict[str, str] = {}  # instance_id -> reason (unsupported size etc.)
        self._order: list[str] = []
        self._idle: str | None = None

    # ---- public --------------------------------------------------------------------

    def get(self, instance_id: str) -> ModuleInstance | None:
        return self.instances.get(instance_id)

    def ordered(self) -> list[ModuleInstance]:
        return [self.instances[i] for i in self._order if i in self.instances]

    async def apply(self, cfg: AppConfig) -> None:
        """Reconcile live instances with the config (create / update / remove) and push rotation."""
        wanted = {e.instance_id: e for e in cfg.modules}
        # Remove
        for instance_id in [i for i in self.instances if i not in wanted]:
            await self._teardown(instance_id)
        self.unavailable = {k: v for k, v in self.unavailable.items() if k in wanted}
        # Create or update
        for entry in cfg.modules:
            existing = self.instances.get(entry.instance_id)
            if existing is None:
                await self._create(entry)
            elif existing.entry.module != entry.module:
                await self._teardown(entry.instance_id)
                await self._create(entry)
            else:
                await self._update(existing, entry)
        self._order = [e.instance_id for e in cfg.modules if e.instance_id in self.instances]
        self._idle = cfg.rotation.idle_module
        self.push_rotation()

    def push_rotation(self) -> None:
        rotation = [inst for inst in self.ordered() if inst.instance_id != self._idle]
        idle = self.instances.get(self._idle) if self._idle else None
        self.scheduler.apply_rotation(rotation, idle)

    async def shutdown(self) -> None:
        for instance_id in list(self.instances):
            await self._teardown(instance_id)

    def settings_changed_sync(self, instance_id: str) -> None:
        """Called after a config write to bump the poller (if any) and re-render."""
        self.scheduler.invalidate(instance_id)

    # ---- internals -----------------------------------------------------------------

    def _context(self, entry: ModuleEntry) -> ModuleContext:
        instance_id = entry.instance_id
        logger = logging.getLogger(f"homely.modules.{entry.module}.{instance_id}")

        def make_poller(
            name: str, every: timedelta, fn: Callable[[], Awaitable[Any]], jitter: float, run_immediately: bool
        ) -> Poller:
            poller = Poller(
                f"{instance_id}:{name}",
                every,
                fn,
                jitter=jitter,
                run_immediately=run_immediately,
                logger=logger,
                now_fn=self.location.now,
            )
            if self.start_pollers:
                poller.start()
            return poller

        def now(tz: tzinfo | None = None) -> datetime:
            return self.location.now(tz)

        return ModuleContext(
            instance_id=instance_id,
            size=self.size,
            orientation=self.orientation,
            location=self.location,
            http=self.http,
            log=logger,
            data_dir=self.data_dir / instance_id,
            now=now,
            make_poller=make_poller,
            invalidate=lambda: self.scheduler.invalidate(instance_id),
            request_takeover=lambda priority, timeout: self.scheduler.request_takeover(instance_id, priority, timeout),
            release_takeover=lambda: self.scheduler.release_takeover(instance_id),
        )

    async def _create(self, entry: ModuleEntry) -> None:
        if not self.registry.has(entry.module):
            self.unavailable[entry.instance_id] = f"unknown module {entry.module!r}"
            log.warning("instance %s: %s", entry.instance_id, self.unavailable[entry.instance_id])
            return
        cls = self.registry.get(entry.module)
        try:
            resolve(cls, self.size)
        except UnsupportedSize:
            self.unavailable[entry.instance_id] = f"{cls.info.name} has no layout for {self.size}"
            log.warning("instance %s: %s", entry.instance_id, self.unavailable[entry.instance_id])
            return
        if self.orientation is Orientation.PORTRAIT and not cls.info.supports_portrait:
            self.unavailable[entry.instance_id] = f"{cls.info.name} does not support portrait"
            return
        settings, err = parse_settings(self.registry, entry)
        ctx = self._context(entry)
        try:
            module = cls(ctx, settings)
            await module.setup()
        except Exception as exc:
            self.unavailable[entry.instance_id] = f"setup failed: {type(exc).__name__}: {exc}"
            log.exception("instance %s setup failed", entry.instance_id)
            for p in ctx.pollers:
                await p.stop()
            return
        self.unavailable.pop(entry.instance_id, None)
        self.instances[entry.instance_id] = ModuleInstance(entry=entry, module=module, settings_error=err)
        log.info("instance %s (%s) ready", entry.instance_id, entry.module)

    async def _update(self, inst: ModuleInstance, entry: ModuleEntry) -> None:
        settings_changed = entry.settings != inst.entry.settings
        inst.entry = entry
        if settings_changed:
            settings, err = parse_settings(self.registry, entry)
            inst.settings_error = err
            try:
                await inst.module.on_settings_changed(settings)
            except Exception as exc:
                log.exception("instance %s on_settings_changed failed", entry.instance_id)
                inst.health.mark_failed(asyncio.get_running_loop().time(), f"{type(exc).__name__}: {exc}")
            for p in inst.module.ctx.pollers:
                p.trigger()
            self.scheduler.invalidate(entry.instance_id)

    async def _teardown(self, instance_id: str) -> None:
        inst = self.instances.pop(instance_id, None)
        if inst is None:
            return
        for p in inst.module.ctx.pollers:
            await p.stop()
        try:
            await inst.module.teardown()
        except Exception:
            log.exception("instance %s teardown failed", instance_id)
        log.info("instance %s removed", instance_id)
