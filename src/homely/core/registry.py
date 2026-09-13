"""Module discovery (built-ins + entry points) and per-instance bookkeeping."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any

from pydantic import ValidationError

from homely.config.models import ModuleEntry
from homely.core.module import Module, ModuleInfo, ModuleSettings
from homely.render.layout import UnsupportedSize, resolve, supported_sizes
from homely.render.size import SUPPORTED_SIZES, Size

log = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "homely.modules"


class ModuleRegistry:
    """Maps module ids to Module classes."""

    def __init__(self, classes: list[type[Module[Any]]] | None = None) -> None:
        self._classes: dict[str, type[Module[Any]]] = {}
        for cls in classes or []:
            self.register(cls)

    def register(self, cls: type[Module[Any]]) -> None:
        info = getattr(cls, "info", None)
        if not isinstance(info, ModuleInfo):
            raise TypeError(f"{cls.__name__} must define a ModuleInfo as `info`")
        if info.id in self._classes and self._classes[info.id] is not cls:
            log.warning("module id %r registered twice; keeping the first", info.id)
            return
        self._classes[info.id] = cls

    def load_entry_points(self) -> None:
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            try:
                cls = ep.load()
                self.register(cls)
            except Exception:
                log.exception("failed to load module entry point %s", ep.name)

    def get(self, module_id: str) -> type[Module[Any]]:
        try:
            return self._classes[module_id]
        except KeyError:
            raise KeyError(f"unknown module {module_id!r}") from None

    def has(self, module_id: str) -> bool:
        return module_id in self._classes

    def all(self) -> list[type[Module[Any]]]:
        return sorted(self._classes.values(), key=lambda c: (c.info.tier.value, c.info.name))

    def ids(self) -> list[str]:
        return sorted(self._classes)

    def schema(self, module_id: str) -> dict[str, Any]:
        return self.get(module_id).Settings.model_json_schema()

    def supports(self, module_id: str, size: Size) -> bool:
        try:
            resolve(self.get(module_id), size)
        except UnsupportedSize:
            return False
        return True

    def sizes_for(self, module_id: str) -> list[Size]:
        return supported_sizes(self.get(module_id), SUPPORTED_SIZES)

    def validate_settings(self, module_id: str, data: dict[str, Any]) -> ModuleSettings:
        """Raises pydantic.ValidationError."""
        return self.get(module_id).Settings.model_validate(data)


@dataclass
class ModuleHealth:
    failures: int = 0
    failed_until: float = 0.0  # monotonic
    last_error: str | None = None
    last_failure_at: float | None = None

    def mark_failed(self, now: float, message: str) -> None:
        self.failures += 1
        self.last_error = message
        self.last_failure_at = now
        cooldown = min(600.0, 60.0 * (2 ** min(self.failures - 1, 4)))
        self.failed_until = now + cooldown

    def is_healthy(self, now: float) -> bool:
        return now >= self.failed_until

    def mark_ok(self) -> None:
        if self.failures and self.last_error is not None:
            # Keep last_error for the UI until a full render succeeds after recovery.
            self.failures = 0
            self.last_error = None


@dataclass
class ModuleInstance:
    entry: ModuleEntry
    module: Module[Any]
    settings_error: str | None = None
    health: ModuleHealth = field(default_factory=ModuleHealth)

    @property
    def instance_id(self) -> str:
        return self.entry.instance_id

    @property
    def module_id(self) -> str:
        return self.entry.module

    @property
    def info(self) -> ModuleInfo:
        return self.module.info

    def enabled(self) -> bool:
        return self.entry.enabled

    def available(self, now: float) -> bool:
        return self.entry.enabled and self.health.is_healthy(now)

    def duration(self, default: float) -> float:
        if self.entry.duration_s is not None:
            return self.entry.duration_s
        try:
            return float(self.module.duration())
        except Exception:
            return default

    def status(self, now: float) -> str:
        if not self.entry.enabled:
            return "disabled"
        if self.settings_error:
            return "error"
        if not self.health.is_healthy(now):
            return "error"
        return "ok"

    def last_error(self) -> str | None:
        return self.settings_error or self.health.last_error


def parse_settings(registry: ModuleRegistry, entry: ModuleEntry) -> tuple[ModuleSettings, str | None]:
    """Validate an entry's settings; on failure fall back to defaults and return the error text."""
    cls = registry.get(entry.module)
    try:
        return cls.Settings.model_validate(entry.settings), None
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        log.warning("instance %s has invalid settings, using defaults: %s", entry.instance_id, msg)
        return cls.Settings(), msg
