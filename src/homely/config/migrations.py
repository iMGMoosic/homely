"""Config schema migrations: each entry upgrades a raw dict from version N to N+1."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homely.config.models import CURRENT_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]

MIGRATIONS: dict[int, Migration] = {}


class FutureConfigVersion(RuntimeError):
    pass


def migrate(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (migrated data, changed?)."""
    version = int(data.get("version", 1))
    if version > CURRENT_VERSION:
        raise FutureConfigVersion(
            f"config version {version} is newer than this homely supports ({CURRENT_VERSION}); upgrade homely"
        )
    changed = False
    while version < CURRENT_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["version"] = version
        changed = True
    return data, changed
