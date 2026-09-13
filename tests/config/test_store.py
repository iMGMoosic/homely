from pathlib import Path

import pytest
import yaml

from homely.config.models import AppConfig, ModuleEntry
from homely.config.store import ConfigError, ConfigStore
from homely.core.events import ConfigChanged, EventBus


def test_creates_default_and_roundtrips(tmp_path: Path):
    path = tmp_path / "config.yaml"
    store = ConfigStore(path, EventBus())
    cfg = store.load()
    assert path.exists()
    assert cfg.modules[0].module == "clock"
    assert AppConfig.model_validate(yaml.safe_load(path.read_text())) == cfg


def test_update_is_atomic_and_publishes(tmp_path: Path):
    path = tmp_path / "config.yaml"
    bus = EventBus()
    events = []
    bus.subscribe(events.append, ConfigChanged)
    store = ConfigStore(path, bus)
    store.load()

    def add(cfg: AppConfig) -> AppConfig:
        cfg.modules.append(ModuleEntry(instance_id="clock-2", module="clock", enabled=False))
        return cfg

    new = store.update(add, scope="modules", instance_id="clock-2")
    assert len(new.modules) == 2
    assert events and events[-1].scope == "modules"
    assert not list(tmp_path.glob("*.tmp"))
    assert store.current == new
    assert ConfigStore(path).load() == new


def test_duplicate_instance_rejected(tmp_path: Path):
    path = tmp_path / "config.yaml"
    store = ConfigStore(path)
    store.load()
    with pytest.raises(ValueError):
        store.update(lambda c: c.model_copy(update={"modules": [c.modules[0], c.modules[0]]}))


def test_invalid_file_raises(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("panel: {rows: 'many'}\n")
    with pytest.raises(ConfigError):
        ConfigStore(path).load()


def test_future_version_rejected(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("version: 99\n")
    with pytest.raises(Exception, match="newer"):
        ConfigStore(path).load()
