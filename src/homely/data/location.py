"""Global location/timezone/units shared by modules."""

from __future__ import annotations

import logging
from datetime import datetime, tzinfo
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

Units = Literal["metric", "imperial"]


class LocationConfig(BaseModel):
    latitude: float | None = Field(None, ge=-90, le=90, title="Latitude")
    longitude: float | None = Field(None, ge=-180, le=180, title="Longitude")
    name: str | None = Field(None, title="Place name", description="e.g. Minneapolis")
    timezone: str | None = Field(
        None,
        title="Timezone",
        description="IANA name; empty uses the system timezone",
        json_schema_extra={"x-widget": "timezone"},
    )
    units: Units = Field("imperial", title="Units")
    locale: str = Field("en_US", title="Locale")


def resolve_tz(name: str | None) -> tzinfo:
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            log.warning("unknown timezone %r, falling back to system", name)
    local = datetime.now().astimezone().tzinfo  # noqa: TID251
    assert local is not None
    return local


class LocationService:
    def __init__(self, cfg: LocationConfig) -> None:
        self._cfg = cfg
        self._tz = resolve_tz(cfg.timezone)

    def update(self, cfg: LocationConfig) -> None:
        self._cfg = cfg
        self._tz = resolve_tz(cfg.timezone)

    @property
    def config(self) -> LocationConfig:
        return self._cfg

    @property
    def tz(self) -> tzinfo:
        return self._tz

    @property
    def latlon(self) -> tuple[float, float] | None:
        if self._cfg.latitude is None or self._cfg.longitude is None:
            return None
        return (self._cfg.latitude, self._cfg.longitude)

    @property
    def units(self) -> Units:
        return self._cfg.units

    def now(self, tz: tzinfo | None = None) -> datetime:
        return datetime.now(tz or self._tz)  # noqa: TID251
