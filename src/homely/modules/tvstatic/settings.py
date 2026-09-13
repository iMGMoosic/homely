from __future__ import annotations

from pydantic import Field

from homely.core.module import ModuleSettings


class TvStaticSettings(ModuleSettings):
    color_noise: bool = Field(
        False,
        title="Color noise",
        description="Off = classic black-and-white snow",
        json_schema_extra={"x-group": "Static", "x-order": 10},
    )
    rolling_bar: bool = Field(True, title="Rolling bar", json_schema_extra={"x-group": "Static", "x-order": 20})
    brightness: int = Field(
        70,
        ge=20,
        le=100,
        title="Snow brightness (%)",
        json_schema_extra={"x-group": "Static", "x-order": 30, "x-widget": "slider"},
    )
    channel_flips: bool = Field(
        True,
        title="Flip channels now and then",
        description="Color bars, test card, NO SIGNAL...",
        json_schema_extra={"x-group": "Channels", "x-order": 10},
    )
    flip_every_s: int = Field(
        8, ge=2, le=60, title="Seconds between flips", json_schema_extra={"x-group": "Channels", "x-order": 20}
    )
    channel_hold_s: float = Field(
        1.5, ge=0.3, le=10, title="Seconds a channel stays on", json_schema_extra={"x-group": "Channels", "x-order": 30}
    )
