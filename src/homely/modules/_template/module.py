"""Example module: scrolls a message. Copy, rename, and edit.

Checklist for a new module:
1. Copy src/homely/modules/_template to src/homely/modules/<id>/ and rename the classes.
2. Fill in ``info`` (id must be unique, lowercase).
3. Declare settings in settings.py; the web UI builds a form from them automatically.
4. Fetch data in ``setup()`` with ``self.ctx.poll(...)``; never do I/O in ``render``.
5. Add ``@layout`` renderers for the sizes you design for and a ``@layout_fallback``.
6. Register the class in src/homely/modules/__init__.py (BUILTIN_MODULES).
7. Add a golden test in tests/modules/.
"""

from __future__ import annotations

from homely.core.module import FrameInfo, Module, ModuleInfo, Tier
from homely.modules._template.settings import ExampleSettings
from homely.render.canvas import Canvas
from homely.render.color import parse_color
from homely.render.fonts import get_font
from homely.render.layout import layout_fallback
from homely.render.text import Marquee


class ExampleModule(Module[ExampleSettings]):
    info = ModuleInfo(
        id="example",
        name="Example",
        description="Scrolls a message. A starting point for new modules.",
        tier=Tier.COOL,
        default_duration_s=10,
        default_fps=30,  # animated: re-render 30 times a second
    )
    Settings = ExampleSettings

    def on_enter(self) -> None:
        font = get_font("6x10")
        self._marquee = Marquee(self.settings.message, font, self.ctx.size.w, speed=self.settings.speed)

    def duration(self) -> float:
        # Show for one full scroll, or the default when the text fits.
        marquee: Marquee | None = getattr(self, "_marquee", None)
        return max(self.info.default_duration_s, marquee.cycle_time() if marquee else 0.0)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        self._marquee.advance(frame.dt)
        y = (c.height - self._marquee.font.line_height) // 2
        self._marquee.draw(c, 0, y, parse_color(self.settings.color))
