"""ConfigStore: load, validate, migrate, atomically save, and announce changes."""

from __future__ import annotations

import logging
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from homely.config.migrations import migrate
from homely.config.models import AppConfig
from homely.core.events import ConfigChanged, EventBus

log = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    pass


def dump_yaml(cfg: AppConfig) -> str:
    return yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


def atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


class ConfigStore:
    def __init__(self, path: Path, bus: EventBus | None = None, *, state_dir: Path | None = None) -> None:
        self.path = path
        self.bus = bus or EventBus()
        self.state_dir = state_dir
        self._lock = threading.RLock()
        self._current: AppConfig | None = None

    # ---- loading -----------------------------------------------------------------

    def load(self, *, create_default: bool = True) -> AppConfig:
        with self._lock:
            if not self.path.exists():
                if not create_default:
                    raise ConfigError(f"config file not found: {self.path}")
                cfg = AppConfig()
                self._write(cfg)
                self._current = cfg
                log.info("created default config at %s", self.path)
                return cfg
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise ConfigError(f"{self.path}: top level must be a mapping")
            data, changed = migrate(raw)
            if changed:
                self._backup(raw)
            try:
                cfg = AppConfig.model_validate(data)
            except ValidationError as exc:
                raise ConfigError(f"{self.path} is invalid:\n{exc}") from exc
            if changed:
                self._write(cfg)
            self._current = cfg
            return cfg

    def _backup(self, raw: dict[str, Any]) -> None:
        if self.state_dir is None:
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        dest = self.state_dir / f"config.backup-v{raw.get('version', 1)}.yaml"
        shutil.copyfile(self.path, dest)
        log.info("backed up pre-migration config to %s", dest)

    @property
    def current(self) -> AppConfig:
        if self._current is None:
            return self.load()
        return self._current

    # ---- saving ------------------------------------------------------------------

    def _write(self, cfg: AppConfig) -> None:
        atomic_write(self.path, dump_yaml(cfg))

    def save(self, cfg: AppConfig, *, scope: str = "all", instance_id: str | None = None) -> None:
        with self._lock:
            old = self._current
            self._write(cfg)
            self._current = cfg
        if old is None or scope != "all" or old != cfg:
            self.bus.publish(ConfigChanged(scope=scope, instance_id=instance_id))  # type: ignore[arg-type]

    def update(
        self,
        fn: Callable[[AppConfig], AppConfig],
        *,
        scope: str = "all",
        instance_id: str | None = None,
    ) -> AppConfig:
        """Read-modify-write under the lock. fn receives a deep copy and returns the new config."""
        with self._lock:
            new_cfg = fn(self.current.model_copy(deep=True))
            new_cfg = AppConfig.model_validate(new_cfg.model_dump(mode="json"))  # re-run validators
            self.save(new_cfg, scope=scope, instance_id=instance_id)
            return new_cfg

    def reload_from_disk(self) -> AppConfig:
        cfg = self.load(create_default=False)
        self.bus.publish(ConfigChanged(scope="all"))
        return cfg
