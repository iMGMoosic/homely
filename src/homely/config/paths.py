"""Where config, secrets and state live."""

from __future__ import annotations

import os
from pathlib import Path

SYSTEM_CONFIG = Path("/etc/homely/config.yaml")
SYSTEM_STATE = Path("/var/lib/homely")


def default_user_config() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "homely" / "config.yaml"


def default_user_state() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "homely"


def resolve_config_path(explicit: str | Path | None = None) -> Path:
    """--config flag > $HOMELY_CONFIG > /etc/homely/config.yaml (if present) > ~/.config/homely."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("HOMELY_CONFIG")
    if env:
        return Path(env).expanduser()
    if SYSTEM_CONFIG.exists():
        return SYSTEM_CONFIG
    return default_user_config()


def resolve_state_dir(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("HOMELY_STATE_DIR")
    if env:
        return Path(env).expanduser()
    if SYSTEM_STATE.is_dir() and os.access(SYSTEM_STATE, os.W_OK):
        return SYSTEM_STATE
    return default_user_state()


def secrets_path_for(config_path: Path) -> Path:
    return config_path.with_name("secrets.yaml")


def fonts_dir_for(config_path: Path) -> Path:
    return config_path.parent / "fonts"
