"""The `homely` command."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import click
import yaml

from homely import __version__


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@click.group(help="homely: a Tidbyt-like LED matrix display for Raspberry Pi.")
@click.version_option(__version__, prog_name="homely")
def main() -> None:
    pass


_config_opt = click.option(
    "--config", "config_path", type=click.Path(), default=None, envvar="HOMELY_CONFIG", help="Config file path"
)
_state_opt = click.option(
    "--state-dir", type=click.Path(), default=None, envvar="HOMELY_STATE_DIR", help="State directory"
)
_backend_opt = click.option(
    "--backend", type=click.Choice(["auto", "rgbmatrix", "none"]), default=None, help="Override display backend"
)


@main.command()
@_config_opt
@_state_opt
@_backend_opt
@click.option("--host", default=None)
@click.option("--port", type=int, default=None)
@click.option(
    "--log-level", default=None, type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False)
)
def run(
    config_path: str | None,
    state_dir: str | None,
    backend: str | None,
    host: str | None,
    port: int | None,
    log_level: str | None,
) -> None:
    """Run the display and the web UI (what the systemd service calls)."""
    from homely.app import Runtime, serve

    _setup_logging(log_level or "INFO")
    try:
        runtime = Runtime(config_path=config_path, state_dir=state_dir, backend=backend)
    except Exception as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    if log_level is None:
        logging.getLogger().setLevel(runtime.cfg.log_level)
    code = asyncio.run(serve(runtime, host=host, port=port, log_level=log_level or runtime.cfg.log_level))
    _exit_or_reexec(code)


def _exit_or_reexec(code: int) -> None:
    """Exit code 3 means "restart requested": re-exec ourselves so it works with or without systemd."""
    from homely.app import RESTART_EXIT_CODE

    if code == RESTART_EXIT_CODE and os.environ.get("HOMELY_NO_REEXEC") != "1":
        click.echo("restarting homely...", err=True)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.executable, [sys.executable, "-m", "homely", *sys.argv[1:]])
    sys.exit(code)


@main.command()
@_config_opt
@_state_opt
@click.option("--port", type=int, default=8080)
@click.option("--no-browser", is_flag=True)
def preview(config_path: str | None, state_dir: str | None, port: int, no_browser: bool) -> None:
    """Run with the emulated display only and open the web UI in a browser."""
    import threading
    import webbrowser

    from homely.app import Runtime, serve

    _setup_logging("INFO")
    runtime = Runtime(config_path=config_path, state_dir=state_dir, backend="none")
    url = f"http://127.0.0.1:{port}/"
    click.echo(f"homely preview at {url}")
    if not no_browser and os.environ.get("HOMELY_REEXEC") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    os.environ["HOMELY_REEXEC"] = "1"  # don't reopen the browser after a restart
    _exit_or_reexec(asyncio.run(serve(runtime, host="0.0.0.0", port=port)))


# `render` needs an offline context; build it here without depending on tests.
def _offline_ctx(size: Any, now: Any) -> Any:
    import logging as _logging
    from datetime import timedelta

    from homely.core.module import ModuleContext
    from homely.data.location import LocationConfig, LocationService
    from homely.data.poller import Poller
    from homely.render.size import Orientation

    loc = LocationService(LocationConfig())

    def make_poller(name: str, every: timedelta, fn: Any, jitter: float, run_immediately: bool) -> Poller:
        return Poller(name, every, fn, jitter=jitter, run_immediately=run_immediately)

    return ModuleContext(
        instance_id="render",
        size=size,
        orientation=Orientation.LANDSCAPE if size.w >= size.h else Orientation.PORTRAIT,
        location=loc,
        http=None,
        log=_logging.getLogger("homely.render"),
        data_dir=Path("."),
        now=lambda tz=None: now.astimezone(tz) if tz else now,
        make_poller=make_poller,
        invalidate=lambda: None,
        request_takeover=lambda p, t: None,
        release_takeover=lambda: None,
    )


@main.command(name="render")
@click.option("--module", "module_id", default="clock", show_default=True)
@click.option("--size", default="64x64", show_default=True)
@click.option("--out", type=click.Path(), default="frame.png", show_default=True)
@click.option("--settings", "settings_json", default="{}", help="Module settings as JSON")
@click.option("--scale", type=int, default=1, help="Integer upscale for viewing")
@click.option("--at", "at_iso", default=None, help="ISO datetime to render at (default: now)")
def render_cmd(module_id: str, size: str, out: str, settings_json: str, scale: int, at_iso: str | None) -> None:
    """Render one frame of a module to a PNG (no hardware, no web server)."""
    from datetime import datetime

    from homely.app import build_registry
    from homely.core.module import FrameInfo
    from homely.render.canvas import Canvas
    from homely.render.size import Size

    registry = build_registry()
    try:
        cls = registry.get(module_id)
    except KeyError:
        click.echo(f"unknown module {module_id!r}; available: {', '.join(registry.ids())}", err=True)
        sys.exit(2)
    sz = Size.parse(size)
    now = datetime.fromisoformat(at_iso) if at_iso else datetime.now().astimezone()  # noqa: TID251
    if now.tzinfo is None:
        now = now.astimezone()
    ctx = _offline_ctx(sz, now)
    module = cls(ctx, cls.Settings.model_validate(json.loads(settings_json)))
    module.on_enter()
    canvas = Canvas(sz)
    module.render(
        canvas, FrameInfo(now=now, monotonic=0.0, dt=0.0, index=0, slot_elapsed=0.0, slot_duration=module.duration())
    )
    img = canvas.upscaled(scale) if scale > 1 else canvas.snapshot()
    img.save(out)
    click.echo(f"wrote {out} ({img.width}x{img.height})")


@main.group()
def modules() -> None:
    """Inspect available modules."""


@modules.command("list")
def modules_list() -> None:
    from homely.app import build_registry

    registry = build_registry()
    for cls in registry.all():
        info = cls.info
        sizes = ", ".join(str(s) for s in registry.sizes_for(info.id))
        click.echo(f"{info.id:<12} {info.tier.value:<5} {info.name:<16} sizes: {sizes}")


@main.group()
def config() -> None:
    """Manage the configuration file."""


@config.command("init")
@_config_opt
@_backend_opt
@click.option("--rows", type=int, default=None)
@click.option("--cols", type=int, default=None)
@click.option("--mapping", type=click.Choice(["regular", "adafruit-hat", "adafruit-hat-pwm"]), default=None)
@click.option("--force", is_flag=True, help="Overwrite an existing file")
def config_init(
    config_path: str | None, backend: str | None, rows: int | None, cols: int | None, mapping: str | None, force: bool
) -> None:
    """Write a default config file."""
    from homely.config.models import AppConfig
    from homely.config.paths import resolve_config_path
    from homely.config.store import ConfigStore

    path = resolve_config_path(config_path)
    if path.exists() and not force:
        click.echo(f"{path} already exists (use --force to overwrite)")
        return
    cfg = AppConfig()
    if backend:
        cfg.display.backend = backend  # type: ignore[assignment]
    if rows:
        cfg.panel.rows = rows
    if cols:
        cfg.panel.cols = cols
    if mapping:
        cfg.panel.hardware_mapping = mapping  # type: ignore[assignment]
    ConfigStore(path).save(cfg)
    click.echo(f"wrote {path}")


@config.command("path")
@_config_opt
def config_path_cmd(config_path: str | None) -> None:
    from homely.config.paths import resolve_config_path

    click.echo(resolve_config_path(config_path))


@config.command("show")
@_config_opt
def config_show(config_path: str | None) -> None:
    from homely.config.paths import resolve_config_path
    from homely.config.store import ConfigStore, dump_yaml

    click.echo(dump_yaml(ConfigStore(resolve_config_path(config_path)).load(create_default=False)), nl=False)


@config.command("validate")
@_config_opt
def config_validate(config_path: str | None) -> None:
    from homely.config.paths import resolve_config_path
    from homely.config.store import ConfigError, ConfigStore

    path = resolve_config_path(config_path)
    try:
        cfg = ConfigStore(path).load(create_default=False)
    except ConfigError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    click.echo(f"{path}: OK ({len(cfg.modules)} module instance(s), panel {cfg.panel.logical})")


@config.command("set")
@_config_opt
@click.argument("key")
@click.argument("value")
def config_set(config_path: str | None, key: str, value: str) -> None:
    """Set a value by dotted path, e.g. `panel.hardware_mapping adafruit-hat-pwm`."""
    from homely.config.models import AppConfig
    from homely.config.paths import resolve_config_path
    from homely.config.store import ConfigStore

    store = ConfigStore(resolve_config_path(config_path))
    data = store.load(create_default=False).model_dump(mode="json")
    parts = key.split(".")
    node: Any = data
    for p in parts[:-1]:
        node = node[int(p)] if isinstance(node, list) else node.setdefault(p, {})
    parsed = yaml.safe_load(value)
    if isinstance(node, list):
        node[int(parts[-1])] = parsed
    else:
        node[parts[-1]] = parsed
    store.save(AppConfig.model_validate(data))
    click.echo(f"set {key} = {parsed!r}")


@config.command("set-password")
@_config_opt
@click.option("--clear", is_flag=True, help="Remove the password and disable auth")
def config_set_password(config_path: str | None, clear: bool) -> None:
    """Protect the web UI with a password (user name is `homely`)."""
    from homely.app import Runtime

    rt = Runtime(config_path=config_path, backend="none", start_pollers=False)
    if clear:
        rt.set_password(None)
        rt.store.update(
            lambda c: c.model_copy(update={"web": c.web.model_copy(update={"auth_enabled": False})}), scope="web"
        )
        click.echo("password cleared; auth disabled")
        return
    pw = click.prompt("New password", hide_input=True, confirmation_prompt=True)
    rt.set_password(pw)
    rt.store.update(
        lambda c: c.model_copy(update={"web": c.web.model_copy(update={"auth_enabled": True})}), scope="web"
    )
    click.echo("password set; auth enabled (restart homely to apply)")


@main.command()
@_config_opt
@_state_opt
def doctor(config_path: str | None, state_dir: str | None) -> None:
    """Check the installation and report problems."""
    from homely.config.paths import resolve_config_path, resolve_state_dir
    from homely.config.store import ConfigError, ConfigStore
    from homely.display.rgbmatrix import rgbmatrix_available
    from homely.render.fonts import available_fonts
    from homely.system import info
    from homely.web.server import STATIC_DIR

    ok = True

    def line(status: bool | None, text: str) -> None:
        nonlocal ok
        mark = "OK " if status else ("-- " if status is None else "!! ")
        if status is False:
            ok = False
        click.echo(f"[{mark}] {text}")

    line(True, f"homely {__version__} on {info.platform_string()}, Python {info.python_version()}")
    path = resolve_config_path(config_path)
    try:
        cfg = ConfigStore(path).load(create_default=False)
        line(True, f"config valid: {path}")
        line(os.access(path, os.W_OK), f"config writable by this user: {path}")
        panel = cfg.panel
        line(
            True,
            f"panel {panel.physical} ({panel.hardware_mapping}, slowdown {panel.gpio_slowdown}) -> {panel.logical}",
        )
    except ConfigError as exc:
        line(False, f"config: {exc}")
        cfg = None
    sd = resolve_state_dir(state_dir)
    line(sd.is_dir() and os.access(sd, os.W_OK) if sd.exists() else None, f"state dir: {sd}")
    linux = sys.platform.startswith("linux")
    have_rgb = rgbmatrix_available()
    line(
        have_rgb if linux else None,
        "rgbmatrix python binding importable" + ("" if linux else " (not needed on this OS)"),
    )
    if linux:
        line(info.is_root() or not have_rgb, "running as root (required to open the LED matrix)")
        line(Path("/dev/mem").exists(), "/dev/mem present")
        cfgtxt = Path("/boot/firmware/config.txt")
        if cfgtxt.exists():
            text = cfgtxt.read_text(errors="ignore")
            line("dtparam=audio=off" in text, "onboard audio disabled in /boot/firmware/config.txt")
        cmdline = Path("/boot/firmware/cmdline.txt")
        if cmdline.exists():
            line(
                True if "isolcpus" in cmdline.read_text(errors="ignore") else None,
                "isolcpus set in cmdline.txt (recommended)",
            )
    fonts = available_fonts()
    line(len(fonts) >= 10, f"{len(fonts)} fonts available")
    line(
        (STATIC_DIR / "index.html").exists(),
        "web UI assets built"
        if (STATIC_DIR / "index.html").exists()
        else "web UI assets missing (run `make build-web`)",
    )
    line(True, f"addresses: {', '.join(info.ip_addresses()) or 'none found'}")
    sys.exit(0 if ok else 1)


@main.command()
def version() -> None:
    click.echo(__version__)


if __name__ == "__main__":
    main()
