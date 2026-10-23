"""Decode a downloaded video into panel-sized RGB frames with ffmpeg.

ffmpeg does all the heavy lifting -- crop, scale, color, speed and frame rate -- and writes raw
frames down a pipe. A reader thread keeps a couple of seconds of them queued; the render thread
takes whichever frame is due. The bounded queue paces ffmpeg, so decoding a few hundred lines of
H.264 costs the Pi very little.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from collections import deque
from dataclasses import dataclass

from homely.modules.video.fetch import VideoFile, find_binary
from homely.modules.video.settings import VideoSettings
from homely.render.size import Size

SCALERS = {"smooth": "area", "sharp": "lanczos", "pixel": "neighbor"}


@dataclass(frozen=True)
class Crop:
    w: int
    h: int
    x: int
    y: int


def crop_box(src_w: int, src_h: int, out: Size, s: VideoSettings) -> Crop:
    """The part of the source picture that ends up on the panel.

    Zoom shrinks the window first; fill then trims it to the panel's shape. Whatever is cut away
    is split according to the focus sliders: 0% keeps the left (or top) edge, 100% the right.
    """
    zoom = s.zoom / 100
    w, h = src_w / zoom, src_h / zoom
    if s.fit == "fill":
        aspect = out.w / out.h
        if w / h > aspect:
            w = h * aspect
        else:
            h = w / aspect
    w, h = max(2, round(w)), max(2, round(h))
    x = round((src_w - w) * s.focus_x / 100)
    y = round((src_h - h) * s.focus_y / 100)
    return Crop(w, h, max(0, x), max(0, y))


def fitted(crop: Crop, out: Size) -> tuple[int, int]:
    """Size of the picture inside the panel for fit: as large as fits, aspect kept."""
    scale = min(out.w / crop.w, out.h / crop.h)
    return max(1, round(crop.w * scale)), max(1, round(crop.h * scale))


def filter_chain(video: VideoFile, out: Size, s: VideoSettings) -> str:
    flags = SCALERS[s.scaling]
    parts: list[str] = []
    if s.speed != 1:
        parts.append(f"setpts=PTS/{s.speed:g}")
    crop = crop_box(video.width, video.height, out, s)
    if (crop.w, crop.h) != (video.width, video.height):
        parts.append(f"crop={crop.w}:{crop.h}:{crop.x}:{crop.y}")
    if s.fit == "fit":
        fw, fh = fitted(crop, out)
        parts.append(f"scale={fw}:{fh}:flags={flags}")
        if (fw, fh) != (out.w, out.h):
            parts.append(f"pad={out.w}:{out.h}:{(out.w - fw) // 2}:{(out.h - fh) // 2}:black")
    else:
        parts.append(f"scale={out.w}:{out.h}:flags={flags}")
    parts.append("setsar=1")
    if s.mirror:
        parts.append("hflip")
    if (s.brightness, s.contrast, s.saturation) != (0, 100, 100):
        parts.append(
            f"eq=brightness={s.brightness / 100:g}:contrast={s.contrast / 100:g}:saturation={s.saturation / 100:g}"
        )
    parts.append(f"fps={s.fps}")
    return ",".join(parts)


def segment(video: VideoFile, s: VideoSettings) -> tuple[float, float | None]:
    """(start, end) of the part of the video that plays, in source seconds; end None = unknown."""
    end = s.end_at or video.duration
    if video.duration:
        end = min(end or video.duration, video.duration)
    start = min(s.start_at, end - 0.5) if end else s.start_at
    return max(0.0, start), end


class Player:
    """One run of a video on the panel: decodes ahead in a thread, hands out the frame due now."""

    def __init__(
        self, video: VideoFile, size: Size, settings: VideoSettings, *, start: float, log: logging.Logger
    ) -> None:
        self.video = video
        self.size = size
        self.settings = settings
        self.log = log
        self.frame_bytes = size.w * size.h * 3
        self.error: str | None = None
        self.ended = False
        self._seg_start, self._seg_end = segment(video, settings)
        self._first_start = start if self._seg_start <= start < (self._seg_end or float("inf")) else self._seg_start
        self._queue: deque[tuple[int, bytes, float]] = deque()
        self._max_queued = max(4, settings.fps * 2)
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._proc: subprocess.Popen[bytes] | None = None
        self._shown_at = self._first_start  # source position of the frame last handed out
        self._thread = threading.Thread(target=self._run, name="video-decode", daemon=True)
        self._thread.start()

    # ---- decoding (reader thread) ------------------------------------------------------------

    def _command(self, start: float) -> list[str]:
        ffmpeg = find_binary("ffmpeg") or "ffmpeg"
        cmd = [ffmpeg, "-nostdin", "-hide_banner", "-v", "fatal", "-ss", f"{start:.3f}"]
        if self._seg_end:
            cmd += ["-t", f"{max(0.1, self._seg_end - start):.3f}"]
        cmd += ["-i", self.video.path, "-an", "-sn", "-dn"]
        cmd += ["-vf", filter_chain(self.video, self.size, self.settings)]
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
        return cmd

    def _run(self) -> None:
        index = 0
        start = self._first_start
        step = self.settings.speed / self.settings.fps  # source seconds per output frame
        while not self._stop.is_set():
            try:
                proc = subprocess.Popen(self._command(start), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except OSError as exc:
                self.error = f"could not run ffmpeg: {exc}"
                break
            self._proc = proc
            assert proc.stdout is not None
            frames = 0
            while not self._stop.is_set():
                data = proc.stdout.read(self.frame_bytes)
                if len(data) < self.frame_bytes:
                    break
                with self._cond:
                    while len(self._queue) >= self._max_queued and not self._stop.is_set():
                        self._cond.wait(0.25)
                    self._queue.append((index, data, start + frames * step))
                index += 1
                frames += 1
            if self._stop.is_set():
                break
            rc = proc.wait()
            stderr = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
            if frames == 0:
                self.error = stderr.splitlines()[-1] if stderr else f"ffmpeg produced no frames (exit {rc})"
                self.log.error("video: %s", self.error)
                break
            if not self.settings.loop:
                break
            start = self._seg_start  # every later pass plays the whole segment
        self.ended = True

    # ---- playback (render thread) ------------------------------------------------------------

    def take(self, t: float) -> bytes | None:
        """The newest frame due by t seconds into this run, or None if none has become due."""
        target = int(t * self.settings.fps)
        frame: bytes | None = None
        with self._cond:
            while self._queue and self._queue[0][0] <= target:
                _, frame, self._shown_at = self._queue.popleft()
            if frame is not None:
                self._cond.notify_all()
        return frame

    @property
    def finished(self) -> bool:
        """Decoding is over and every frame has been shown."""
        return self.ended and not self._queue

    def position(self) -> float:
        """Source time of the frame on the panel, for picking up there next turn."""
        return self._shown_at

    def close(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2)
        if proc is not None:
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
            proc.wait(timeout=2)
