"""Built-in modules. Add new module classes to BUILTIN_MODULES."""

from __future__ import annotations

from typing import Any

from homely.core.module import Module
from homely.modules.clock import ClockModule
from homely.modules.lavalamp import LavaLampModule
from homely.modules.life import LifeModule
from homely.modules.lightcycles import LightCyclesModule
from homely.modules.maze import MazeModule
from homely.modules.news import NewsModule
from homely.modules.pipes import PipesModule
from homely.modules.qix import QixModule
from homely.modules.skyline import SkylineModule
from homely.modules.snake import SnakeModule
from homely.modules.starfield import StarfieldModule
from homely.modules.tree import TreeModule
from homely.modules.tvstatic import TvStaticModule
from homely.modules.weather import WeatherModule


def builtin_modules() -> list[type[Module[Any]]]:
    return [
        ClockModule,
        WeatherModule,
        NewsModule,
        MazeModule,
        QixModule,
        StarfieldModule,
        PipesModule,
        LifeModule,
        LavaLampModule,
        TvStaticModule,
        SnakeModule,
        TreeModule,
        SkylineModule,
        LightCyclesModule,
    ]


BUILTIN_MODULES = builtin_modules()
