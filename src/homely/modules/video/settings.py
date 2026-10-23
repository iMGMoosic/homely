from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from homely.core.module import ModuleSettings


class VideoSettings(ModuleSettings):
    url: str = Field(
        "",
        title="Video link",
        description="A YouTube link (anything yt-dlp can download works). It is downloaded once and kept on the Pi.",
        json_schema_extra={"x-group": "Video", "x-order": 10, "x-placeholder": "https://www.youtube.com/watch?v=..."},
    )
    start_at: float = Field(
        0, ge=0, title="Start at (seconds)", json_schema_extra={"x-group": "Video", "x-order": 20, "x-unit": " s"}
    )
    end_at: float = Field(
        0,
        ge=0,
        title="Stop at (seconds)",
        description="0 plays to the end of the video",
        json_schema_extra={"x-group": "Video", "x-order": 30, "x-unit": " s"},
    )
    max_height: Literal[144, 240, 360, 480] = Field(
        360,
        title="Download quality (lines)",
        description="The panel needs very little; more only helps when zoomed in. Higher costs disk and CPU.",
        json_schema_extra={"x-group": "Video", "x-order": 40},
    )

    loop: bool = Field(
        True,
        title="Loop",
        description="Start over when the video ends",
        json_schema_extra={"x-group": "Playback", "x-order": 10},
    )
    turn_seconds: int = Field(
        0,
        ge=0,
        le=3600,
        title="Time on the board each turn (seconds)",
        description=(
            "0 = one play-through. Longer than the video: it loops to fill the time when Loop is on, "
            "otherwise the turn ends with the video."
        ),
        json_schema_extra={"x-group": "Playback", "x-order": 20},
    )
    resume: bool = Field(
        False,
        title="Pick up where it left off",
        description="Off starts the video from the beginning every turn",
        json_schema_extra={"x-group": "Playback", "x-order": 30},
    )
    speed: float = Field(
        1.0,
        ge=0.25,
        le=4.0,
        multiple_of=0.25,
        title="Speed",
        json_schema_extra={"x-group": "Playback", "x-order": 40, "x-widget": "slider", "x-unit": "x"},
    )
    fps: int = Field(
        30,
        ge=5,
        le=30,
        title="Frame rate",
        description="Lower saves CPU on the Pi; the panel never shows more than 30",
        json_schema_extra={"x-group": "Playback", "x-order": 50, "x-widget": "slider", "x-unit": " fps"},
    )

    fit: Literal["fill", "fit", "stretch"] = Field(
        "fill",
        title="Fit",
        description=(
            "fill = crop to cover the whole panel; fit = the whole picture with black bars; "
            "stretch = squash the whole picture onto the panel"
        ),
        json_schema_extra={"x-group": "Picture", "x-order": 10},
    )
    zoom: int = Field(
        100,
        ge=100,
        le=400,
        title="Zoom",
        description="Crop further into the picture",
        json_schema_extra={"x-group": "Picture", "x-order": 20, "x-widget": "slider", "x-unit": "%"},
    )
    focus_x: int = Field(
        50,
        ge=0,
        le=100,
        title="Crop position: left to right",
        description="Which part of the picture to keep when it is cropped (fill, or zoomed in)",
        json_schema_extra={"x-group": "Picture", "x-order": 30, "x-widget": "slider", "x-unit": "%"},
    )
    focus_y: int = Field(
        50,
        ge=0,
        le=100,
        title="Crop position: top to bottom",
        json_schema_extra={"x-group": "Picture", "x-order": 40, "x-widget": "slider", "x-unit": "%"},
    )
    mirror: bool = Field(False, title="Mirror", json_schema_extra={"x-group": "Picture", "x-order": 50})
    scaling: Literal["smooth", "sharp", "pixel"] = Field(
        "smooth",
        title="Scaling",
        description="smooth averages pixels (best for most video); sharp keeps edges crisper; pixel is blocky",
        json_schema_extra={"x-group": "Picture", "x-order": 60},
    )
    brightness: int = Field(
        0,
        ge=-50,
        le=50,
        title="Brightness",
        json_schema_extra={"x-group": "Picture", "x-order": 70, "x-widget": "slider"},
    )
    contrast: int = Field(
        100,
        ge=50,
        le=200,
        title="Contrast",
        json_schema_extra={"x-group": "Picture", "x-order": 80, "x-widget": "slider", "x-unit": "%"},
    )
    saturation: int = Field(
        100,
        ge=0,
        le=300,
        title="Color saturation",
        json_schema_extra={"x-group": "Picture", "x-order": 90, "x-widget": "slider", "x-unit": "%"},
    )
    show_title: bool = Field(
        False,
        title="Show the title at the start of each turn",
        json_schema_extra={"x-group": "Picture", "x-order": 100},
    )

    @field_validator("url")
    @classmethod
    def _http(cls, v: str) -> str:
        v = v.strip()
        if v and not v.lower().startswith(("http://", "https://")):
            raise ValueError("must be a link starting with https://")
        return v

    @model_validator(mode="after")
    def _end_after_start(self) -> VideoSettings:
        if self.end_at and self.end_at <= self.start_at:
            raise ValueError("'Stop at' must be after 'Start at' (or 0 for the end of the video)")
        return self
