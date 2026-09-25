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


def test_reload_from_disk_publishes_only_changed_sections(tmp_path):
    import time

    from homely.config.store import ConfigStore
    from homely.core.events import ConfigChanged, EventBus

    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(lambda e: seen.append(e.scope), ConfigChanged)
    store = ConfigStore(tmp_path / "config.yaml", bus)
    store.load()
    assert not store.changed_on_disk()
    text = store.path.read_text().replace("level: 60", "level: 33")
    time.sleep(0.02)
    store.path.write_text(text)
    import os

    os.utime(store.path, (time.time() + 5, time.time() + 5))  # make sure mtime differs
    assert store.changed_on_disk()
    cfg = store.reload_from_disk()
    assert cfg.brightness.level == 33
    assert seen == ["brightness"]
    assert not store.changed_on_disk()


def test_old_config_drops_the_removed_pipes_and_tv_static_modules(tmp_path: Path):
    """They were cut in 0.2.3; a config that still lists them loads without "unknown module"
    rows, keeps everything else, and is backed up before it is rewritten."""
    path = tmp_path / "config.yaml"
    state = tmp_path / "state"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "rotation": {"idle_module": "static"},
                "modules": [
                    {"instance_id": "clock", "module": "clock"},
                    {"instance_id": "pipes", "module": "pipes", "duration_s": 90},
                    {"instance_id": "static", "module": "tvstatic"},
                    {"instance_id": "maze", "module": "maze"},
                ],
            }
        )
    )
    cfg = ConfigStore(path, EventBus(), state_dir=state).load()
    assert [m.instance_id for m in cfg.modules] == ["clock", "maze"]
    assert cfg.rotation.idle_module is None  # it pointed at the removed static instance
    assert cfg.version == 2
    on_disk = yaml.safe_load(path.read_text())
    assert on_disk["version"] == 2 and [m["module"] for m in on_disk["modules"]] == ["clock", "maze"]
    backup = yaml.safe_load((state / "config.backup-v1.yaml").read_text())
    assert [m["module"] for m in backup["modules"]] == ["clock", "pipes", "tvstatic", "maze"]


def test_idle_module_survives_the_migration_when_it_was_not_removed(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "rotation": {"idle_module": "maze"},
                "modules": [{"instance_id": "maze", "module": "maze"}, {"instance_id": "p", "module": "pipes"}],
            }
        )
    )
    cfg = ConfigStore(path, EventBus()).load()
    assert cfg.rotation.idle_module == "maze" and [m.module for m in cfg.modules] == ["maze"]
