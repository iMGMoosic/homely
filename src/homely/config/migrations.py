"""Config schema migrations: each entry upgrades a raw dict from version N to N+1."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from homely.config.models import CURRENT_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]

# Built-in modules that have since been removed. Their entries are dropped rather than left to
# show up forever as "unknown module" rows the user has to delete by hand.
RETIRED_MODULES = frozenset({"pipes", "tvstatic"})


def _drop_retired_modules(data: dict[str, Any]) -> dict[str, Any]:
    """v1 -> v2: the pipes and TV static animations were removed in 0.2.3."""
    modules = data.get("modules")
    if not isinstance(modules, list):
        return data
    gone = {m.get("instance_id") for m in modules if isinstance(m, dict) and m.get("module") in RETIRED_MODULES}
    data["modules"] = [m for m in modules if not (isinstance(m, dict) and m.get("module") in RETIRED_MODULES)]
    rotation = data.get("rotation")
    if isinstance(rotation, dict) and rotation.get("idle_module") in gone:
        rotation["idle_module"] = None
    return data


MIGRATIONS: dict[int, Migration] = {1: _drop_retired_modules}


class FutureConfigVersion(RuntimeError):
    pass


def migrate(raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (migrated data, changed?). `raw` itself is left untouched, so a caller can still
    back it up as it was -- including under its original version number."""
    data = copy.deepcopy(raw)
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
