"""API request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from homely.core.module import Tier


class ApiError(BaseModel):
    path: str
    message: str
    type: str


class ApiErrors(BaseModel):
    errors: list[ApiError]


class ModuleCatalogEntry(BaseModel):
    id: str
    name: str
    description: str
    tier: Tier
    icon: str | None
    supports_portrait: bool
    default_duration_s: float
    allow_multiple: bool
    supported_sizes: list[str]
    supports_current_size: bool
    schema_: dict[str, Any] = Field(serialization_alias="schema")
    defaults: dict[str, Any]


class RotationItem(BaseModel):
    instance_id: str
    module: str
    name: str
    enabled: bool
    duration_s: float | None
    effective_duration_s: float
    settings: dict[str, Any]
    status: str  # ok | error | disabled | unavailable
    last_error: str | None
    is_current: bool
    is_idle: bool


class RotationPatch(BaseModel):
    enabled: bool | None = None
    duration_s: float | None = Field(None, ge=1, le=600)
    clear_duration: bool = False


class RotationOrder(BaseModel):
    order: list[str]


class RotationAdd(BaseModel):
    module: str
    instance_id: str | None = None
    enabled: bool = True


class PinRequest(BaseModel):
    pinned: bool = True


class SettingsPayload(BaseModel):
    rotation: dict[str, Any]
    brightness: dict[str, Any]
    location: dict[str, Any]
    schema_: dict[str, dict[str, Any]] = Field(serialization_alias="schema")


class SettingsUpdate(BaseModel):
    rotation: dict[str, Any] | None = None
    brightness: dict[str, Any] | None = None
    location: dict[str, Any] | None = None


class BrightnessUpdate(BaseModel):
    level: int = Field(ge=0, le=100)


class HardwarePayload(BaseModel):
    panel: dict[str, Any]
    display: dict[str, Any]
    web: dict[str, Any]
    schema_: dict[str, dict[str, Any]] = Field(serialization_alias="schema")
    requires_restart: bool = True
    restart_pending: bool


class HardwareUpdate(BaseModel):
    panel: dict[str, Any] | None = None
    display: dict[str, Any] | None = None
    web: dict[str, Any] | None = None


class SystemInfo(BaseModel):
    version: str
    hostname: str
    ip_addresses: list[str]
    uptime_s: float
    started_at: float
    backend: str
    hardware_available: bool
    size: str
    orientation: str
    cpu_temp_c: float | None
    python: str
    platform: str
    config_path: str
    state_dir: str
    auth_enabled: bool
    restart_pending: bool
    render_fps: float
    target_fps: int
    last_error: str | None


class ActionResult(BaseModel):
    ok: bool
    message: str


class StateInfo(BaseModel):
    phase: str
    current: str | None
    current_module: str | None
    pinned: str | None
    takeover: str | None
    slot_elapsed: float
    slot_duration: float
    brightness: int
    fps: float
    rotation: list[str]


class GeocodeResult(BaseModel):
    name: str
    admin1: str | None = None
    country: str | None = None
    latitude: float
    longitude: float
    timezone: str | None = None
    label: str


class TransitChoice(BaseModel):
    id: str
    label: str


class LogLine(BaseModel):
    ts: str
    level: str
    logger: str
    message: str
