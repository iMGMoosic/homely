"""Stub modules for scheduler tests."""

from __future__ import annotations

from homely.config.models import ModuleEntry
from homely.core.module import FrameInfo, Module, ModuleInfo, ModuleSettings, Tier
from homely.core.registry import ModuleInstance
from homely.render.canvas import Canvas
from homely.render.layout import layout_fallback
from homely.render.size import Size
from tests.conftest import make_ctx


class StubModule(Module[ModuleSettings]):
    info = ModuleInfo(id="stub", name="Stub", description="", tier=Tier.COOL, default_duration_s=5)
    color = (10, 20, 30)
    display = True
    fps_value = 0
    raise_in_render = False
    raise_in_should_display = False

    def __init__(self, ctx, settings):
        super().__init__(ctx, settings)
        self.renders = 0
        self.enters = 0
        self.exits = 0

    def should_display(self) -> bool:
        if self.raise_in_should_display:
            raise RuntimeError("boom-sd")
        return self.display

    def fps(self) -> int:
        return self.fps_value

    def on_enter(self) -> None:
        self.enters += 1

    def on_exit(self) -> None:
        self.exits += 1

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        if self.raise_in_render:
            raise RuntimeError("boom-render")
        self.renders += 1
        c.clear(self.color)


def make_instance(
    instance_id: str, *, color=(10, 20, 30), enabled=True, duration=None, fps=0, display=True, size=Size(8, 8)
) -> ModuleInstance:
    mod = StubModule(make_ctx(size), ModuleSettings())
    mod.color = color
    mod.display = display
    mod.fps_value = fps
    entry = ModuleEntry(instance_id=instance_id, module="stub", enabled=enabled, duration_s=duration)
    return ModuleInstance(entry=entry, module=mod)
