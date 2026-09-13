"""Brightness level, night schedule and temporary overrides."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time

from pydantic import BaseModel, Field


class BrightnessRule(BaseModel):
    start: str = Field("22:00", pattern=r"^\d{2}:\d{2}$", title="From", json_schema_extra={"format": "time"})
    end: str = Field("07:00", pattern=r"^\d{2}:\d{2}$", title="Until", json_schema_extra={"format": "time"})
    brightness: int = Field(
        10,
        ge=0,
        le=100,
        title="Brightness",
        description="0 turns the display off",
        json_schema_extra={"x-widget": "slider"},
    )


class BrightnessSchedule(BaseModel):
    enabled: bool = Field(False, title="Night schedule")
    rules: list[BrightnessRule] = Field(default_factory=lambda: [BrightnessRule()], title="Rules")


class BrightnessConfig(BaseModel):
    level: int = Field(60, ge=0, le=100, title="Brightness", json_schema_extra={"x-widget": "slider", "x-unit": "%"})
    schedule: BrightnessSchedule = Field(default_factory=BrightnessSchedule, title="Schedule")


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def rule_active(rule: BrightnessRule, now: datetime) -> bool:
    start, end = _parse_hhmm(rule.start), _parse_hhmm(rule.end)
    t = now.time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # wraps midnight


class BrightnessController:
    def __init__(self, cfg: BrightnessConfig, now_fn: Callable[[], datetime]) -> None:
        self._cfg = cfg
        self._now = now_fn
        self._override: tuple[int, float] | None = None  # (level, expires_at_monotonic)

    def update_config(self, cfg: BrightnessConfig) -> None:
        self._cfg = cfg

    @property
    def level(self) -> int:
        return self._cfg.level

    def set_level(self, level: int) -> None:
        self._cfg = self._cfg.model_copy(update={"level": max(0, min(100, level))})

    def override(self, level: int, for_s: float, monotonic_now: float) -> None:
        self._override = (max(0, min(100, level)), monotonic_now + for_s)

    def effective(self, monotonic_now: float | None = None) -> int:
        if self._override is not None and monotonic_now is not None:
            level, expires = self._override
            if monotonic_now < expires:
                return level
            self._override = None
        if self._cfg.schedule.enabled:
            now = self._now()
            for rule in self._cfg.schedule.rules:
                if rule_active(rule, now):
                    return rule.brightness
        return self._cfg.level
