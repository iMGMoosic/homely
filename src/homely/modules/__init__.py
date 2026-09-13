"""Built-in modules. Add new module classes to BUILTIN_MODULES."""

from __future__ import annotations

from typing import Any

from homely.core.module import Module
from homely.modules.clock import ClockModule
from homely.modules.maze import MazeModule
from homely.modules.news import NewsModule
from homely.modules.qix import QixModule
from homely.modules.weather import WeatherModule


def builtin_modules() -> list[type[Module[Any]]]:
    return [ClockModule, WeatherModule, NewsModule, MazeModule, QixModule]


BUILTIN_MODULES = builtin_modules()
