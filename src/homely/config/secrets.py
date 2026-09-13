"""Secrets live in secrets.yaml (0600), keyed by instance_id then field path.

Module settings models mark secret fields with ``pydantic.SecretStr``; the API redacts
them to ``{"$secret": true}`` and accepts blank/missing (= keep) or null (= clear).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr

REDACTED: dict[str, bool] = {"$secret": True}


def secret_field_names(model: type[BaseModel]) -> set[str]:
    names: set[str] = set()
    for name, field in model.model_fields.items():
        ann = field.annotation
        if ann is SecretStr:
            names.add(name)
        else:
            args = getattr(ann, "__args__", ())
            if SecretStr in args:
                names.add(name)
    return names


class SecretStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, str]] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            raw = yaml.safe_load(self.path.read_text()) or {}
            self._data = {str(k): {str(a): str(b) for a, b in (v or {}).items()} for k, v in raw.items()}
        else:
            self._data = {}

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".yaml.tmp")
            tmp.write_text(yaml.safe_dump(self._data, sort_keys=True))
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)

    def get(self, instance_id: str, field: str) -> str | None:
        return self._data.get(instance_id, {}).get(field)

    def set(self, instance_id: str, field: str, value: str | None) -> None:
        bucket = self._data.setdefault(instance_id, {})
        if value is None:
            bucket.pop(field, None)
            if not bucket:
                self._data.pop(instance_id, None)
        else:
            bucket[field] = value

    def remove_instance(self, instance_id: str) -> None:
        self._data.pop(instance_id, None)

    # ---- helpers used by the config store / API --------------------------------

    def merge(self, instance_id: str, model: type[BaseModel], public: dict[str, Any]) -> dict[str, Any]:
        """Return public settings with stored secrets filled in for validation."""
        out = dict(public)
        for name in secret_field_names(model):
            incoming = out.get(name, REDACTED)
            if incoming == REDACTED or incoming == "" or (isinstance(incoming, dict) and incoming.get("$secret")):
                stored = self.get(instance_id, name)
                if stored is not None:
                    out[name] = stored
                else:
                    out.pop(name, None)
        return out

    def extract(self, instance_id: str, model: type[BaseModel], settings: BaseModel) -> dict[str, Any]:
        """Store secret fields from a validated settings model; return the public dict."""
        public = settings.model_dump(mode="json")
        for name in secret_field_names(model):
            value = getattr(settings, name, None)
            if isinstance(value, SecretStr):
                self.set(instance_id, name, value.get_secret_value())
            elif value is None:
                self.set(instance_id, name, None)
            public.pop(name, None)
        return public

    def redact(self, instance_id: str, model: type[BaseModel], public: dict[str, Any]) -> dict[str, Any]:
        out = dict(public)
        for name in secret_field_names(model):
            out[name] = REDACTED if self.get(instance_id, name) is not None else None
        return out
