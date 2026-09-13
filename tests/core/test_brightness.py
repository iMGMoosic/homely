from datetime import datetime

from homely.core.brightness import BrightnessConfig, BrightnessController, BrightnessRule, BrightnessSchedule


def ctl(hour, minute=0, rules=None, level=60):
    now = datetime(2026, 1, 1, hour, minute)
    cfg = BrightnessConfig(level=level, schedule=BrightnessSchedule(enabled=rules is not None, rules=rules or []))
    return BrightnessController(cfg, lambda: now)


def test_plain_level():
    assert ctl(12).effective() == 60


def test_night_rule_wraps_midnight():
    rules = [BrightnessRule(start="22:00", end="07:00", brightness=5)]
    assert ctl(23, rules=rules).effective() == 5
    assert ctl(3, rules=rules).effective() == 5
    assert ctl(7, rules=rules).effective() == 60
    assert ctl(21, 59, rules=rules).effective() == 60


def test_override_expires():
    c = ctl(12)
    c.override(100, for_s=10, monotonic_now=0.0)
    assert c.effective(5.0) == 100
    assert c.effective(11.0) == 60


def test_set_level_clamps():
    c = ctl(12)
    c.set_level(500)
    assert c.level == 100
