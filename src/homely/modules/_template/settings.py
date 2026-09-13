"""Settings for the example module. Copy this directory to start a new module."""

from __future__ import annotations

from pydantic import Field

from homely.core.module import ModuleSettings


class ExampleSettings(ModuleSettings):
    message: str = Field("Hello", title="Message", max_length=64, json_schema_extra={"x-order": 10})
    color: str = Field(
        "#00A8FF", title="Color", pattern=r"^#[0-9A-Fa-f]{6}$", json_schema_extra={"format": "color", "x-order": 20}
    )
    speed: int = Field(
        20, title="Scroll speed", ge=5, le=80, json_schema_extra={"x-widget": "slider", "x-unit": "px/s"}
    )
