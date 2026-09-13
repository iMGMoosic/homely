"""Runtime: the composition root. One process = render thread + asyncio (web, pollers)."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import platform
import secrets as pysecrets
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from homely import __version__
from homely.config.models import AppConfig, ModuleEntry
from homely.config.paths import fonts_dir_for, resolve_config_path, resolve_state_dir, secrets_path_for
from homely.config.secrets import SecretStore
from homely.config.store import ConfigStore
from homely.core.brightness import BrightnessController
from homely.core.events import BrightnessChanged, ConfigChanged, EventBus, RestartRequested
from homely.core.instances import InstanceManager
from homely.core.loop import RenderLoop
from homely.core.registry import ModuleRegistry
from homely.core.scheduler import Scheduler
from homely.core.transitions import make_transition
from homely.data.http import make_client
from homely.data.location import LocationService
from homely.display.base import Display
from homely.display.composite import CompositeDisplay
from homely.display.framebus import FrameBus
from homely.display.recording import NullDisplay
from homely.display.rgbmatrix import RgbMatrixDisplay, rgbmatrix_available
from homely.display.web import WebDisplay
from homely.modules import BUILTIN_MODULES
from homely.render.fonts import add_font_dir
from homely.render.size import Size
from homely.system import info as sysinfo
from homely.web import schemas

log = logging.getLogger(__name__)

RESTART_EXIT_CODE = 3
PASSWORD_KEY = ("_web", "password_hash")


def build_registry() -> ModuleRegistry:
    registry = ModuleRegistry(BUILTIN_MODULES)
    registry.load_entry_points()
    return registry


class Runtime:
    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        state_dir: str | Path | None = None,
        backend: str | None = None,
        registry: ModuleRegistry | None = None,
        start_pollers: bool = True,
    ) -> None:
        self.version = __version__
        self.config_path = resolve_config_path(config_path)
        self.state_dir = resolve_state_dir(state_dir)
        self.bus = EventBus()
        self.store = ConfigStore(self.config_path, self.bus, state_dir=self.state_dir)
        self.secrets = SecretStore(secrets_path_for(self.config_path))
        self.registry = registry or build_registry()
        self._backend_override = backend
        self._start_pollers = start_pollers

        cfg = self.store.load()
        self.backend = self._choose_backend(cfg)
        self.hardware_available = rgbmatrix_available()
        self.size: Size = cfg.logical_size(self.backend == "rgbmatrix")
        self.orientation = cfg.panel.orientation

        self.framebus = FrameBus()
        self.display: Display = self._build_display(cfg)
        self.location = LocationService(cfg.location)
        self.brightness = BrightnessController(cfg.brightness, self.location.now)
        self.scheduler = Scheduler(
            self.size,
            transition=make_transition(cfg.rotation.transition, cfg.rotation.transition_duration_s),
            now_fn=self.location.now,
            default_duration=cfg.rotation.default_duration_s,
            on_event=self.bus.publish,
        )
        self.loop = RenderLoop(self.scheduler, self.display, self.brightness, target_fps=cfg.rotation.target_fps)
        self.http: httpx.AsyncClient | None = None
        self.instances: InstanceManager | None = None
        self.started_at = time.time()
        self.restart_pending = False
        self.exit_code: int | None = None
        self._listener: asyncio.Task[None] | None = None
        self._unsub: Any = None
        self.on_exit_request: Any = None
        self._started = False

    # ---- construction helpers ---------------------------------------------------

    def _choose_backend(self, cfg: AppConfig) -> str:
        choice = self._backend_override or cfg.display.backend
        if choice == "auto":
            return "rgbmatrix" if rgbmatrix_available() and sys.platform.startswith("linux") else "none"
        return choice

    def _build_display(self, cfg: AppConfig) -> Display:
        displays: list[Display] = []
        if self.backend == "rgbmatrix":
            displays.append(RgbMatrixDisplay(cfg.panel, initial_brightness=cfg.brightness.level))
        if cfg.display.preview or not displays:
            displays.append(WebDisplay(self.framebus, self.size))
        if not displays:
            displays.append(NullDisplay(self.size))
        return displays[0] if len(displays) == 1 else CompositeDisplay(displays)

    @property
    def cfg(self) -> AppConfig:
        return self.store.current

    # ---- lifecycle --------------------------------------------------------------

    def open_display(self) -> None:
        """Open the display first: on hardware this is where root privileges are dropped."""
        self.display.open()

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.open_display()
        fonts_dir = fonts_dir_for(self.config_path)
        if fonts_dir.is_dir():
            add_font_dir(fonts_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.http = make_client()
        self.instances = InstanceManager(
            self.registry,
            self.scheduler,
            size=self.size,
            orientation=self.orientation,
            location=self.location,
            http=self.http,
            data_dir=self.state_dir / "modules",
            start_pollers=self._start_pollers,
        )
        await self.instances.apply(self.cfg)
        self.loop.start()
        queue, self._unsub = self.bus.subscribe_async(ConfigChanged)
        self._listener = asyncio.create_task(self._config_listener(queue), name="config-listener")
        log.info(
            "homely %s started: backend=%s size=%s config=%s", self.version, self.backend, self.size, self.config_path
        )

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._listener
        if self._unsub:
            self._unsub()
        self.loop.stop()
        if self.instances is not None:
            await self.instances.shutdown()
        if self.http is not None:
            await self.http.aclose()
        self.display.close()

    def request_restart(self, reason: str) -> None:
        self.exit_code = RESTART_EXIT_CODE
        self.bus.publish(RestartRequested(reason=reason))
        if self.on_exit_request is not None:
            self.on_exit_request()

    async def _config_listener(self, queue: asyncio.Queue[Any]) -> None:
        while True:
            event: ConfigChanged = await queue.get()
            try:
                await self._apply_change(event)
            except Exception:
                log.exception("failed to apply config change %r", event)

    async def _apply_change(self, event: ConfigChanged) -> None:
        cfg = self.cfg
        scope = event.scope
        if scope in ("panel", "display", "web", "all"):
            self.restart_pending = True
        if scope in ("location", "all"):
            self.location.update(cfg.location)
        if scope in ("brightness", "all"):
            self.brightness.update_config(cfg.brightness)
            self.bus.publish(BrightnessChanged(level=self.brightness.effective()))
        if scope in ("rotation", "all"):
            self.scheduler.transition = make_transition(cfg.rotation.transition, cfg.rotation.transition_duration_s)
            self.scheduler.default_duration = cfg.rotation.default_duration_s
            self.loop.set_target_fps(cfg.rotation.target_fps)
        if scope in ("modules", "rotation", "all") and self.instances is not None:
            await self.instances.apply(cfg)

    # ---- auth -------------------------------------------------------------------

    def auth_required(self) -> bool:
        return bool(self.cfg.web.auth_enabled and self.secrets.get(*PASSWORD_KEY))

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> str:
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return f"{salt.hex()}${digest.hex()}"

    def set_password(self, password: str | None) -> None:
        if password:
            self.secrets.set(*PASSWORD_KEY, self._hash_password(password, os.urandom(16)))
        else:
            self.secrets.set(*PASSWORD_KEY, None)
        self.secrets.save()

    def check_password(self, password: str) -> bool:
        stored = self.secrets.get(*PASSWORD_KEY)
        if not stored or "$" not in stored:
            return False
        salt_hex, _ = stored.split("$", 1)
        return pysecrets.compare_digest(stored, self._hash_password(password, bytes.fromhex(salt_hex)))

    # ---- API facades ------------------------------------------------------------

    def catalog(self) -> list[schemas.ModuleCatalogEntry]:
        out = []
        for cls in self.registry.all():
            info = cls.info
            out.append(
                schemas.ModuleCatalogEntry(
                    id=info.id,
                    name=info.name,
                    description=info.description,
                    tier=info.tier,
                    icon=info.icon,
                    supports_portrait=info.supports_portrait,
                    default_duration_s=info.default_duration_s,
                    allow_multiple=info.allow_multiple,
                    supported_sizes=[str(s) for s in self.registry.sizes_for(info.id)],
                    supports_current_size=self.registry.supports(info.id, self.size),
                    schema_=self.registry.schema(info.id),
                    defaults=cls.Settings().model_dump(mode="json"),
                )
            )
        return out

    def _item(self, entry: ModuleEntry) -> schemas.RotationItem:
        now = time.monotonic()
        inst = self.instances.get(entry.instance_id) if self.instances else None
        unavailable = self.instances.unavailable.get(entry.instance_id) if self.instances else None
        cls = self.registry.get(entry.module) if self.registry.has(entry.module) else None
        name = cls.info.name if cls else entry.module
        settings = entry.settings
        if cls is not None:
            try:
                settings = cls.Settings.model_validate(
                    self.secrets.merge(entry.instance_id, cls.Settings, entry.settings)
                ).model_dump(mode="json")
            except ValidationError:
                settings = {**cls.Settings().model_dump(mode="json"), **entry.settings}
            settings = self.secrets.redact(entry.instance_id, cls.Settings, settings)
        if inst is not None:
            status = inst.status(now)
            last_error = inst.last_error()
            effective = inst.duration(self.cfg.rotation.default_duration_s)
        else:
            status = "unavailable" if unavailable or cls is None else ("disabled" if not entry.enabled else "ok")
            last_error = unavailable or (None if cls else f"unknown module {entry.module!r}")
            effective = entry.duration_s or (
                cls.info.default_duration_s if cls else self.cfg.rotation.default_duration_s
            )
        state = self.scheduler.state()
        return schemas.RotationItem(
            instance_id=entry.instance_id,
            module=entry.module,
            name=name,
            enabled=entry.enabled,
            duration_s=entry.duration_s,
            effective_duration_s=effective,
            settings=settings,
            status=status,
            last_error=last_error,
            is_current=state.current == entry.instance_id,
            is_idle=self.cfg.rotation.idle_module == entry.instance_id,
        )

    def rotation_items(self) -> list[schemas.RotationItem]:
        return [self._item(e) for e in self.cfg.modules]

    def rotation_item(self, instance_id: str) -> schemas.RotationItem:
        entry = self.cfg.entry(instance_id)
        if entry is None:
            raise KeyError(instance_id)
        return self._item(entry)

    def update_instance_settings(self, instance_id: str, data: dict[str, Any]) -> schemas.RotationItem:
        entry = self.cfg.entry(instance_id)
        if entry is None:
            raise KeyError(instance_id)
        cls = self.registry.get(entry.module)
        merged = self.secrets.merge(instance_id, cls.Settings, data)
        model = cls.Settings.model_validate(merged)  # raises ValidationError -> 422
        public = self.secrets.extract(instance_id, cls.Settings, model)
        self.secrets.save()

        def mutate(cfg: AppConfig) -> AppConfig:
            e = cfg.entry(instance_id)
            assert e is not None
            e.settings = public
            return cfg

        self.store.update(mutate, scope="modules", instance_id=instance_id)
        return self.rotation_item(instance_id)

    def patch_instance(self, instance_id: str, patch: schemas.RotationPatch) -> schemas.RotationItem:
        if self.cfg.entry(instance_id) is None:
            raise KeyError(instance_id)

        def mutate(cfg: AppConfig) -> AppConfig:
            e = cfg.entry(instance_id)
            assert e is not None
            if patch.enabled is not None:
                e.enabled = patch.enabled
            if patch.clear_duration:
                e.duration_s = None
            elif patch.duration_s is not None:
                e.duration_s = patch.duration_s
            return cfg

        self.store.update(mutate, scope="modules", instance_id=instance_id)
        return self.rotation_item(instance_id)

    def reorder(self, order: list[str]) -> list[schemas.RotationItem]:
        existing = {e.instance_id for e in self.cfg.modules}
        if set(order) != existing or len(order) != len(existing):
            raise ValueError("order must list every instance exactly once")

        def mutate(cfg: AppConfig) -> AppConfig:
            by_id = {e.instance_id: e for e in cfg.modules}
            cfg.modules = [by_id[i] for i in order]
            return cfg

        self.store.update(mutate, scope="modules")
        return self.rotation_items()

    def add_instance(self, module: str, instance_id: str | None = None, enabled: bool = True) -> schemas.RotationItem:
        cls = self.registry.get(module)  # KeyError if unknown
        existing = {e.instance_id for e in self.cfg.modules}
        if any(e.module == module for e in self.cfg.modules) and not cls.info.allow_multiple:
            raise ValueError(f"{cls.info.name} does not allow multiple instances")
        if instance_id is None:
            instance_id = module
            n = 2
            while instance_id in existing:
                instance_id = f"{module}-{n}"
                n += 1
        elif instance_id in existing:
            raise ValueError(f"instance {instance_id!r} already exists")
        entry = ModuleEntry(instance_id=instance_id, module=module, enabled=enabled)

        def mutate(cfg: AppConfig) -> AppConfig:
            cfg.modules.append(entry)
            return cfg

        self.store.update(mutate, scope="modules", instance_id=instance_id)
        return self.rotation_item(instance_id)

    def remove_instance(self, instance_id: str) -> None:
        if self.cfg.entry(instance_id) is None:
            raise KeyError(instance_id)

        def mutate(cfg: AppConfig) -> AppConfig:
            cfg.modules = [e for e in cfg.modules if e.instance_id != instance_id]
            if cfg.rotation.idle_module == instance_id:
                cfg.rotation.idle_module = None
            return cfg

        self.store.update(mutate, scope="modules", instance_id=instance_id)
        self.secrets.remove_instance(instance_id)
        self.secrets.save()

    def pin(self, instance_id: str, pinned: bool) -> None:
        if self.cfg.entry(instance_id) is None:
            raise KeyError(instance_id)
        self.scheduler.pin(instance_id if pinned else None)

    def settings_payload(self) -> schemas.SettingsPayload:
        cfg = self.cfg
        return schemas.SettingsPayload(
            rotation=cfg.rotation.model_dump(mode="json"),
            brightness=cfg.brightness.model_dump(mode="json"),
            location=cfg.location.model_dump(mode="json"),
            schema_={
                "rotation": type(cfg.rotation).model_json_schema(),
                "brightness": type(cfg.brightness).model_json_schema(),
                "location": type(cfg.location).model_json_schema(),
            },
        )

    def update_settings(self, update: schemas.SettingsUpdate) -> schemas.SettingsPayload:
        scopes: list[str] = []

        def mutate(cfg: AppConfig) -> AppConfig:
            if update.rotation is not None:
                cfg.rotation = type(cfg.rotation).model_validate(update.rotation)
                scopes.append("rotation")
            if update.brightness is not None:
                cfg.brightness = type(cfg.brightness).model_validate(update.brightness)
                scopes.append("brightness")
            if update.location is not None:
                cfg.location = type(cfg.location).model_validate(update.location)
                scopes.append("location")
            return cfg

        self.store.update(mutate, scope="all" if len(scopes) != 1 else scopes[0])
        return self.settings_payload()

    def set_brightness(self, level: int) -> int:
        def mutate(cfg: AppConfig) -> AppConfig:
            cfg.brightness.level = level
            return cfg

        self.store.update(mutate, scope="brightness")
        return self.brightness.effective(time.monotonic())

    def hardware_payload(self) -> schemas.HardwarePayload:
        cfg = self.cfg
        return schemas.HardwarePayload(
            panel=cfg.panel.model_dump(mode="json"),
            display=cfg.display.model_dump(mode="json"),
            web=cfg.web.model_dump(mode="json"),
            schema_={
                "panel": type(cfg.panel).model_json_schema(),
                "display": type(cfg.display).model_json_schema(),
                "web": type(cfg.web).model_json_schema(),
            },
            restart_pending=self.restart_pending,
        )

    def update_hardware(self, update: schemas.HardwareUpdate) -> schemas.HardwarePayload:
        def mutate(cfg: AppConfig) -> AppConfig:
            if update.panel is not None:
                cfg.panel = type(cfg.panel).model_validate(update.panel)
            if update.display is not None:
                cfg.display = type(cfg.display).model_validate(update.display)
            if update.web is not None:
                cfg.web = type(cfg.web).model_validate(update.web)
            return cfg

        self.store.update(mutate, scope="panel")
        return self.hardware_payload()

    def state(self) -> schemas.StateInfo:
        st = self.scheduler.state()
        return schemas.StateInfo(
            phase=st.phase,
            current=st.current,
            current_module=st.current_module,
            pinned=st.pinned,
            takeover=st.takeover,
            slot_elapsed=st.slot_elapsed,
            slot_duration=st.slot_duration if st.slot_duration != float("inf") else -1,
            brightness=self.brightness.effective(time.monotonic()),
            fps=round(self.loop.measured_fps, 1),
            rotation=list(st.rotation),
        )

    def system_info(self) -> schemas.SystemInfo:
        return schemas.SystemInfo(
            version=self.version,
            hostname=sysinfo.hostname(),
            ip_addresses=sysinfo.ip_addresses(),
            uptime_s=time.time() - self.started_at,
            started_at=self.started_at,
            backend=self.backend,
            hardware_available=self.hardware_available,
            size=str(self.size),
            orientation=self.orientation.value,
            cpu_temp_c=sysinfo.cpu_temp_c(),
            python=sysinfo.python_version(),
            platform=sysinfo.platform_string()
            if sys.platform.startswith("linux")
            else f"{platform.system()} {platform.machine()}",
            config_path=str(self.config_path),
            state_dir=str(self.state_dir),
            auth_enabled=self.auth_required(),
            restart_pending=self.restart_pending,
            render_fps=round(self.loop.measured_fps, 1),
            target_fps=self.loop.target_fps,
            last_error=self.loop.last_error,
        )

    async def run_action(self, name: str) -> schemas.ActionResult:
        from homely.system import actions

        if name == "restart-renderer":
            self.request_restart("requested from web UI")
            return schemas.ActionResult(ok=True, message="restarting homely")
        if name == "test-pattern":
            self.loop.show_test_pattern(5.0)
            return schemas.ActionResult(ok=True, message="showing test pattern for 5 seconds")
        if name == "reload-config":
            self.store.reload_from_disk()
            return schemas.ActionResult(ok=True, message="config reloaded from disk")
        if name == "next":
            self.scheduler.next()
            return schemas.ActionResult(ok=True, message="skipped to next module")
        if name == "prev":
            self.scheduler.prev()
            return schemas.ActionResult(ok=True, message="went back one module")
        if name == "reboot":
            ok, msg = await actions.reboot()
            return schemas.ActionResult(ok=ok, message=msg)
        if name == "shutdown":
            ok, msg = await actions.shutdown()
            return schemas.ActionResult(ok=ok, message=msg)
        raise KeyError(name)


async def serve(runtime: Runtime, host: str | None = None, port: int | None = None, log_level: str = "info") -> int:
    """Start the runtime and the web server; returns the process exit code."""
    import uvicorn

    from homely.web.server import create_app

    await runtime.start()
    app = create_app(runtime)
    config = uvicorn.Config(
        app,
        host=host or runtime.cfg.web.host,
        port=port or runtime.cfg.web.port,
        log_level=log_level.lower(),
        access_log=False,
        lifespan="off",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    runtime.on_exit_request = lambda: setattr(server, "should_exit", True)
    try:
        await server.serve()
    finally:
        await runtime.stop()
    return runtime.exit_code or 0
