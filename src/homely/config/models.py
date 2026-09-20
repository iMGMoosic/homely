"""Top-level configuration models. PanelConfig maps 1:1 onto hzeller's RGBMatrixOptions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from homely.core.brightness import BrightnessConfig
from homely.data.location import LocationConfig
from homely.render.size import Orientation, Size

CURRENT_VERSION = 1

HardwareMapping = Literal["regular", "adafruit-hat", "adafruit-hat-pwm", "classic", "regular-pi1", "classic-pi1"]


class PanelConfig(BaseModel):
    """Physical panel and driver options. Changing these requires a renderer restart."""

    model_config = ConfigDict(json_schema_extra={"x-requires-restart": True})

    rows: int = Field(64, ge=8, le=64, description="Rows per panel")
    cols: int = Field(64, ge=16, le=128, description="Columns per panel")
    chain_length: int = Field(1, ge=1, le=8, description="Panels chained horizontally")
    parallel: int = Field(1, ge=1, le=3, description="Parallel chains")
    hardware_mapping: HardwareMapping = Field(
        "adafruit-hat",
        description="Use adafruit-hat-pwm only if you soldered the GPIO4-GPIO18 jumper on the Bonnet",
    )
    gpio_slowdown: int = Field(4, ge=0, le=5, description="Pi 4 usually needs 2-4")
    pwm_bits: int = Field(11, ge=1, le=11)
    pwm_lsb_nanoseconds: int = Field(130, ge=50, le=3000)
    pwm_dither_bits: int = Field(0, ge=0, le=2)
    led_rgb_sequence: str = Field("RGB", pattern=r"^[RGB]{3}$")
    panel_type: str = Field("", description="Leave empty; set FM6126A or FM6127 if the panel stays dark")
    multiplexing: int = Field(0, ge=0, le=17)
    row_address_type: int = Field(0, ge=0, le=5)
    scan_mode: int = Field(0, ge=0, le=1)
    pixel_mapper_config: str = Field(
        "", description="e.g. U-mapper for chained panels; rotation is added automatically"
    )
    limit_refresh_rate_hz: int = Field(0, ge=0, le=1000, description="0 = unlimited; 120-150 is a good Pi 4 value")
    disable_hardware_pulsing: bool = False
    inverse_colors: bool = False
    show_refresh_rate: bool = False
    drop_privileges: bool = True
    drop_priv_user: str = "homely"
    drop_priv_group: str = "homely"
    orientation: Orientation = Orientation.LANDSCAPE
    rotate_direction: Literal[90, 270] = Field(90, description="Which way portrait rotates")
    gamma: float = Field(1.0, ge=0.5, le=4.0, description="1.0 = off; try 2.2 if colors look washed out")

    @property
    def physical(self) -> Size:
        return Size(self.cols * self.chain_length, self.rows * self.parallel)

    @property
    def logical(self) -> Size:
        return self.physical.rotated() if self.orientation is Orientation.PORTRAIT else self.physical


class DisplayConfig(BaseModel):
    backend: Literal["auto", "rgbmatrix", "none"] = Field(
        "auto",
        title="Backend",
        description="auto = hardware when the rgbmatrix library is importable, else preview only",
    )
    preview: bool = Field(True, title="Live preview", description="Publish frames to the web UI")
    emulated_size: str | None = Field(
        None, title="Emulated size", description="Logical size when running without hardware, e.g. 64x32"
    )

    @field_validator("emulated_size")
    @classmethod
    def _valid_size(cls, v: str | None) -> str | None:
        if v is not None:
            Size.parse(v)
        return v


class WebConfig(BaseModel):
    host: str = Field("0.0.0.0", title="Listen address")
    port: int = Field(8080, ge=1, le=65535, title="Port")
    preview_fps: int = Field(20, ge=1, le=30, title="Live preview frame rate")
    auth_enabled: bool = Field(False, title="Require password", description="Set one with `homely config set-password`")


# Keep in sync with homely.core.transitions.TRANSITION_NAMES (a test asserts they match).
TransitionName = Literal[
    "cut",
    "fade",
    "fade_black",
    "slide_left",
    "slide_right",
    "slide_up",
    "slide_down",
    "wipe_left",
    "wipe_right",
    "wipe_up",
    "wipe_down",
    "curtain_h",
    "curtain_v",
    "blinds",
    "iris",
    "dissolve",
    "pixelate",
    "glitch",
    "random",
]


class RotationConfig(BaseModel):
    default_duration_s: float = Field(15, ge=1, le=600, title="Default time per module (seconds)")
    transition: TransitionName = Field("fade", title="Transition")
    transition_duration_s: float = Field(0.4, ge=0, le=3, title="Transition length (seconds)")
    target_fps: int = Field(30, ge=1, le=60, title="Render rate (fps)", description="30 is plenty; 60 for fast games")
    idle_module: str | None = Field(
        None, title="Idle module", description="Instance id shown when every other module has nothing to display"
    )


class ModuleEntry(BaseModel):
    instance_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,40}$")
    module: str
    enabled: bool = True
    duration_s: float | None = Field(None, ge=1, le=600)
    settings: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = CURRENT_VERSION
    panel: PanelConfig = Field(default_factory=PanelConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    location: LocationConfig = Field(default_factory=LocationConfig)
    rotation: RotationConfig = Field(default_factory=RotationConfig)
    brightness: BrightnessConfig = Field(default_factory=BrightnessConfig)
    modules: list[ModuleEntry] = Field(default_factory=lambda: [ModuleEntry(instance_id="clock", module="clock")])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("modules")
    @classmethod
    def _unique_instances(cls, v: list[ModuleEntry]) -> list[ModuleEntry]:
        seen: set[str] = set()
        for entry in v:
            if entry.instance_id in seen:
                raise ValueError(f"duplicate instance_id {entry.instance_id!r}")
            seen.add(entry.instance_id)
        return v

    def entry(self, instance_id: str) -> ModuleEntry | None:
        return next((e for e in self.modules if e.instance_id == instance_id), None)

    def logical_size(self, hardware_present: bool) -> Size:
        if not hardware_present and self.display.emulated_size:
            return Size.parse(self.display.emulated_size)
        return self.panel.logical
