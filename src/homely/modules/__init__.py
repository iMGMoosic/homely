"""Built-in modules. Add new module classes to BUILTIN_MODULES."""

from __future__ import annotations

from typing import Any

from homely.core.module import Module
from homely.modules.clock import ClockModule


def builtin_modules() -> list[type[Module[Any]]]:
    return [ClockModule]


BUILTIN_MODULES = builtin_modules()
