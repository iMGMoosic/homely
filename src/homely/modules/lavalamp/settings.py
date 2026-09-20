from __future__ import annotations

from typing import Literal

from pydantic import Field

from homely.core.module import ModuleSettings


class LavaLampSettings(ModuleSettings):
    blobs: int = Field(
        5, ge=2, le=12, title="Blobs", json_schema_extra={"x-group": "Lava", "x-order": 10, "x-widget": "slider"}
    )
    speed: int = Field(
        30, ge=5, le=100, title="Speed", json_schema_extra={"x-group": "Lava", "x-order": 20, "x-widget": "slider"}
    )
    blob_size: int = Field(
        24,
        ge=10,
        le=45,
        title="Blob size (% of the panel)",
        json_schema_extra={"x-group": "Lava", "x-order": 30, "x-widget": "slider"},
    )
    palette: Literal[
        "classic", "ocean", "toxic", "sunset", "ember", "berry", "cyber", "mint", "gold", "ice", "custom"
    ] = Field("classic", title="Palette", json_schema_extra={"x-group": "Colors", "x-order": 10})
    lava_color: str = Field(
        "#FF4A1C",
        title="Lava (custom)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 20},
    )
    glow_color: str = Field(
        "#FFB000",
        title="Lava core (custom)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 30},
    )
    background_color: str = Field(
        "#2A0A3A",
        title="Background (custom)",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Colors", "format": "color", "x-order": 40},
    )
