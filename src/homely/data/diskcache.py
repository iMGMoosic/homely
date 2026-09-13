"""Small JSON cache per module instance so a restart shows last-known data immediately."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class DiskCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, name: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
        return self.directory / f"{safe}.json"

    def get(self, name: str, max_age_s: float | None = None) -> Any | None:
        path = self._path(name)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        saved_at = float(raw.get("saved_at", 0))
        if max_age_s is not None and time.time() - saved_at > max_age_s:
            return None
        return raw.get("data")

    def saved_at(self, name: str) -> float | None:
        try:
            return float(json.loads(self._path(name).read_text(encoding="utf-8")).get("saved_at", 0))
        except (OSError, ValueError):
            return None

    def set(self, name: str, data: Any) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(name)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"saved_at": time.time(), "data": data}), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            log.warning("disk cache write failed for %s: %s", name, exc)

    def delete(self, name: str) -> None:
        with contextlib.suppress(OSError):
            self._path(name).unlink()
