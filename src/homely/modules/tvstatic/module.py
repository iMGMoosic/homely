"""Retro TV static: snow, a rolling bar and scanlines, and every so often the set flips to a
channel (color bars, a test card, NO SIGNAL, PLEASE STAND BY) before tearing back to static."""

from __future__ import annotations

import random
from enum import Enum

from PIL import Image, ImageChops

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.modules.tvstatic.settings import TvStaticSettings
from homely.render.canvas import Canvas
from homely.render.color import WHITE
from homely.render.fonts import get_font
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.text import fit_text

SMPTE = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]


class Mode(Enum):
    STATIC = "static"
    CHANNEL = "channel"
    TEAR = "tear"


class TvStaticModule(Module[TvStaticSettings]):
    info = ModuleInfo(
        id="tvstatic",
        name="TV static",
        description="Idle animation: analog snow with a rolling bar, and the occasional channel flip.",
        tier=Tier.NEED,
        icon="tvstatic",
        default_duration_s=45,
        default_fps=30,
        min_size=Size(16, 16),
    )
    Settings = TvStaticSettings

    def __init__(self, ctx: ModuleContext, settings: TvStaticSettings, *, seed: int | None = None) -> None:
        super().__init__(ctx, settings)
        self.rng = random.Random(seed)
        self._scan: Image.Image | None = None
        self._reset()

    def _reset(self) -> None:
        self.mode = Mode.STATIC
        self.timer = 0.0
        self.next_flip = self.rng.uniform(self.settings.flip_every_s * 0.6, self.settings.flip_every_s * 1.4)
        self.bar_y = 0.0
        self.channel = 0

    def on_enter(self) -> None:
        # Every turn tunes in fresh, rather than resuming a half-finished channel flip.
        self._reset()

    def _scanlines(self, size: Size) -> Image.Image:
        if self._scan is None or self._scan.size != size.as_tuple():
            rows = bytes(255 if y % 2 == 0 else 165 for y in range(size.h) for _ in range(size.w))
            self._scan = Image.frombytes("L", size.as_tuple(), rows)
        return self._scan

    def _noise(self, size: Size) -> Image.Image:
        n = size.w * size.h
        k = self.settings.brightness / 100
        if self.settings.color_noise:
            chans = [
                Image.frombytes("L", size.as_tuple(), self.rng.randbytes(n)).point(lambda v: int(v * k))
                for _ in range(3)
            ]
            return Image.merge("RGB", chans)
        gray = Image.frombytes("L", size.as_tuple(), self.rng.randbytes(n)).point(lambda v: int(v * k))
        return Image.merge("RGB", (gray, gray, gray))

    def _static(self, size: Size, dt: float) -> Image.Image:
        img = self._noise(size)
        if self.settings.rolling_bar:
            self.bar_y = (self.bar_y + dt * size.h * 0.6) % (size.h * 1.4)
            bar_h = max(3, size.h // 6)
            band = Image.new("L", size.as_tuple(), 0)
            top = int(self.bar_y) - bar_h
            for i in range(bar_h):
                y = top + i
                if 0 <= y < size.h:
                    v = int(90 * (1 - abs(i - bar_h / 2) / (bar_h / 2)))
                    band.paste(v, (0, y, size.w, y + 1))
            img = ImageChops.add(img, Image.merge("RGB", (band, band, band)))
        scan = self._scanlines(size)
        return ImageChops.multiply(img, Image.merge("RGB", (scan, scan, scan)))

    def _channel_image(self, size: Size) -> Image.Image:
        img = Image.new("RGB", size.as_tuple(), (0, 0, 0))
        c = Canvas(size, image=img)
        kind = self.channel % 4
        if kind == 0:  # color bars
            bar_w = size.w / len(SMPTE)
            for i, col in enumerate(SMPTE):
                c.rect(int(i * bar_w), 0, int((i + 1) * bar_w) - int(i * bar_w), int(size.h * 0.7), fill=col)
            steps = 8
            for i in range(steps):
                v = int(255 * i / (steps - 1))
                c.rect(int(i * size.w / steps), int(size.h * 0.7), int(size.w / steps) + 1, size.h, fill=(v, v, v))
        elif kind == 1:  # test card: crosshair, circle, gray ring
            cx, cy = size.w // 2, size.h // 2
            c.rect(0, 0, size.w, size.h, fill=(30, 30, 30))
            for i in range(0, size.w, max(4, size.w // 8)):
                c.vline(i, 0, size.h, (70, 70, 70))
            for j in range(0, size.h, max(4, size.h // 8)):
                c.hline(0, j, size.w, (70, 70, 70))
            r = min(size.w, size.h) // 2 - 2
            from PIL import ImageDraw

            d = ImageDraw.Draw(img)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(220, 220, 220))
            d.ellipse((cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2), outline=(220, 160, 60))
            c.hline(0, cy, size.w, WHITE)
            c.vline(cx, 0, size.h, WHITE)
        elif kind == 2:  # NO SIGNAL on blue
            c.rect(0, 0, size.w, size.h, fill=(0, 0, 160))
            font, text = fit_text("NO SIGNAL", [get_font(n) for n in ("6x10", "5x8", "4x6", "tom-thumb")], size.w - 2)
            c.text(size.w // 2, size.h // 2 - font.line_height // 2, text, font, WHITE, halign="center")
        else:  # PLEASE STAND BY
            c.rect(0, 0, size.w, size.h, fill=(20, 20, 20))
            font, text = fit_text("PLEASE", [get_font(n) for n in ("6x10", "5x8", "4x6", "tom-thumb")], size.w - 2)
            c.text(size.w // 2, size.h // 2 - font.line_height - 1, text, font, (255, 200, 60), halign="center")
            font2, text2 = fit_text("STAND BY", [get_font(n) for n in ("6x10", "5x8", "4x6", "tom-thumb")], size.w - 2)
            c.text(size.w // 2, size.h // 2 + 1, text2, font2, (255, 200, 60), halign="center")
        return img

    def _tear(self, img: Image.Image, size: Size, strength: float) -> Image.Image:
        """Horizontal tearing: shift bands of rows sideways by random amounts."""
        out = img.copy()
        band = max(2, size.h // 10)
        for y in range(0, size.h, band):
            shift = int(self.rng.uniform(-1, 1) * size.w * 0.3 * strength)
            if shift:
                strip = img.crop((0, y, size.w, min(size.h, y + band)))
                out.paste(strip, (shift, y))
                out.paste(strip, (shift - size.w if shift > 0 else shift + size.w, y))
        return out

    def advance(self, dt: float) -> None:
        self.timer += dt
        if self.mode is Mode.STATIC:
            if self.settings.channel_flips and self.timer >= self.next_flip:
                self.mode, self.timer = Mode.CHANNEL, 0.0
                self.channel = self.rng.randrange(4)
        elif self.mode is Mode.CHANNEL:
            if self.timer >= self.settings.channel_hold_s:
                self.mode, self.timer = Mode.TEAR, 0.0
        elif self.timer >= 0.35:
            self.mode, self.timer = Mode.STATIC, 0.0
            self.next_flip = self.rng.uniform(self.settings.flip_every_s * 0.6, self.settings.flip_every_s * 1.4)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        dt = min(frame.dt, 0.25)
        self.advance(dt)
        if self.mode is Mode.STATIC:
            img = self._static(c.size, dt)
        elif self.mode is Mode.CHANNEL:
            img = self._channel_image(c.size)
            if self.timer < 0.15:  # settle in with a bit of tearing
                img = self._tear(img, c.size, 1 - self.timer / 0.15)
        else:
            static = self._static(c.size, dt)
            img = ImageChops.blend(
                self._tear(self._channel_image(c.size), c.size, 1.0), static, min(1.0, self.timer / 0.35)
            )
        c.blit(img, 0, 0)
        if self.mode is Mode.STATIC and self.rng.random() < 0.05:  # occasional flicker
            c.blit(img.point(lambda v: int(v * 0.6)), 0, 0)
