"""RenderLoop: a fixed-tick thread that drives the scheduler and pushes frames to displays."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from PIL import Image

from homely.core.brightness import BrightnessController
from homely.core.scheduler import Scheduler
from homely.display.base import Display

log = logging.getLogger(__name__)


class RenderLoop(threading.Thread):
    def __init__(
        self,
        scheduler: Scheduler,
        display: Display,
        brightness: BrightnessController,
        *,
        target_fps: int = 30,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(name="homely-render", daemon=True)
        self.scheduler = scheduler
        self.display = display
        self.brightness = brightness
        self.target_fps = max(1, target_fps)
        self._clock = clock
        self._sleep = sleep
        self._stop_event = threading.Event()
        self._last_brightness: int | None = None
        self._black = Image.new("RGB", scheduler.size.as_tuple())
        self._showing_black = False
        self.frames = 0
        self.measured_fps = 0.0
        self.last_error: str | None = None
        self._test_until = 0.0
        self._test_frame: Image.Image | None = None

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self.is_alive():
            self.join(timeout)

    def set_target_fps(self, fps: int) -> None:
        self.target_fps = max(1, fps)

    def show_test_pattern(self, seconds: float = 5.0) -> None:
        """Show color bars for a few seconds (called from any thread)."""
        self._test_until = self._clock() + seconds
        self._test_frame = None

    def _render_test_pattern(self) -> Image.Image:
        from homely.render.canvas import Canvas

        w, h = self.scheduler.size.as_tuple()
        c = Canvas(self.scheduler.size)
        bars = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 0, 0), (0, 0, 255)]
        bw = max(1, w // len(bars))
        for i, color in enumerate(bars):
            c.rect(i * bw, 0, bw if i < len(bars) - 1 else w - i * bw, h * 2 // 3, fill=color)
        steps = 8
        sw = max(1, w // steps)
        for i in range(steps):
            v = int(255 * i / (steps - 1))
            c.rect(i * sw, h * 2 // 3, sw if i < steps - 1 else w - i * sw, h - h * 2 // 3, fill=(v, v, v))
        c.rect(0, 0, w, h, outline=(255, 255, 255))
        c.line(0, 0, w - 1, h - 1, (255, 255, 255))
        return c.snapshot()

    def step(self, t: float) -> None:
        """One tick; separated from run() so tests can drive it."""
        level = self.brightness.effective(t)
        if level != self._last_brightness:
            self.display.set_brightness(level)
            self._last_brightness = level
        if t < self._test_until:
            if self._test_frame is None:
                self._test_frame = self._render_test_pattern()
                self.display.show(self._test_frame)
            return
        if self._test_frame is not None:
            self._test_frame = None
            frame = self.scheduler.tick(t) or self.scheduler.last_output
            if frame is not None:
                self.display.show(frame)
            return
        if level == 0:
            if not self._showing_black:
                self.display.show(self._black)
                self._showing_black = True
            # Keep the scheduler advancing so the rotation resumes naturally.
            self.scheduler.tick(t)
            return
        frame = self.scheduler.tick(t)
        if self._showing_black:
            self._showing_black = False
            if frame is None:
                frame = self.scheduler.last_output  # re-show the current frame after waking
        if frame is not None:
            self.display.show(frame)
            self.frames += 1

    def run(self) -> None:
        interval = 1.0 / self.target_fps
        next_tick = self._clock()
        fps_window_start = next_tick
        fps_frames = 0
        while not self._stop_event.is_set():
            t = self._clock()
            try:
                self.step(t)
                fps_frames += 1
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("render loop error")
            if t - fps_window_start >= 1.0:
                self.measured_fps = fps_frames / (t - fps_window_start)
                fps_window_start = t
                fps_frames = 0
            interval = 1.0 / self.target_fps
            next_tick += interval
            delay = next_tick - self._clock()
            if delay > 0:
                self._sleep(delay)
            else:
                next_tick = self._clock()  # fell behind: don't try to catch up
