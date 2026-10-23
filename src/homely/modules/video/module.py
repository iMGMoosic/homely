"""Video: plays a YouTube video (or anything yt-dlp can fetch) on the panel.

The video is downloaded once, at low resolution, and kept on the Pi; each turn ffmpeg decodes it
straight to panel-sized frames with the crop, zoom, color and speed settings applied.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from PIL import Image

from homely.core.module import FrameInfo, Module, ModuleContext, ModuleInfo, Tier
from homely.data.slot import DataSlot
from homely.modules.video.fetch import Downloader, VideoError, VideoFile, find_binary
from homely.modules.video.player import Player, segment
from homely.modules.video.settings import VideoSettings
from homely.render.canvas import Canvas
from homely.render.color import AMBER, dim
from homely.render.fonts import get_font
from homely.render.layout import layout_fallback
from homely.render.size import Size
from homely.render.status import draw_status_card
from homely.render.text import ScrollingLabels

RECHECK = timedelta(hours=12)  # re-run the (normally no-op) download check this often
TITLE_SECONDS = 6.0
STATUS_TURN_S = 10.0
# Settings that change what ffmpeg is asked for: a change restarts the player in place.
PLAYER_FIELDS = (
    "start_at", "end_at", "loop", "speed", "fps", "fit", "zoom", "focus_x", "focus_y", "mirror",
    "scaling", "brightness", "contrast", "saturation",
)  # fmt: skip


class VideoModule(Module[VideoSettings]):
    info = ModuleInfo(
        id="video",
        name="Video",
        description="Plays a YouTube video, with loop, crop, zoom and color controls.",
        tier=Tier.COOL,
        icon="video",
        default_duration_s=30,
        default_fps=30,
        min_size=Size(32, 32),
        allow_multiple=True,
    )
    Settings = VideoSettings

    def __init__(self, ctx: ModuleContext, settings: VideoSettings) -> None:
        super().__init__(ctx, settings)
        self.video: DataSlot[VideoFile] = DataSlot()
        self.progress: float | None = None  # 0..1 while downloading
        self.error: VideoError | None = None
        self._downloader = Downloader(ctx.data_dir / "video", ctx.log)
        self._player: Player | None = None
        self._restart = False
        self._clock = 0.0
        self._resume_at: float | None = None
        self._last: bytes | None = None
        self._labels = ScrollingLabels()

    # ---- data --------------------------------------------------------------------------

    async def setup(self) -> None:
        cached = self._downloader.cached(self.settings.url, self.settings.max_height) if self.settings.url else None
        if cached:
            self.video.set(cached, self.ctx.now())
        self.ctx.poll("download", RECHECK, self._ensure_downloaded)

    async def teardown(self) -> None:
        self._close_player()

    async def on_settings_changed(self, settings: VideoSettings) -> None:
        old = self.settings
        self.settings = settings
        if (settings.url, settings.max_height) != (old.url, old.max_height):
            self.video.clear()
            self.error = None
            self._resume_at = None
            self._restart = True
            for p in self.ctx.pollers:
                p.trigger()
        elif any(getattr(settings, f) != getattr(old, f) for f in PLAYER_FIELDS):
            if (settings.start_at, settings.end_at) != (old.start_at, old.end_at):
                self._resume_at = None
            self._restart = True  # picked up by the render thread, which owns the player
        self.ctx.invalidate()

    async def _ensure_downloaded(self) -> None:
        url, height = self.settings.url, self.settings.max_height
        if not url:
            return
        cached = self._downloader.cached(url, height)
        if cached is not None:
            if self.video.value != cached:
                self.video.set(cached, self.ctx.now())
            return
        self.error = None
        self.progress = 0.0
        self.ctx.invalidate()
        try:
            video = await asyncio.to_thread(self._downloader.download, url, height, self._on_progress)
        except VideoError as exc:
            self.error = exc
            raise
        except Exception as exc:
            self.error = VideoError(str(exc), "see the logs")
            raise
        finally:
            self.progress = None
        if (self.settings.url, self.settings.max_height) != (url, height):
            return  # the link changed while this one downloaded; the next run fetches the new one
        self.video.set(video, self.ctx.now())
        self._restart = True
        self.ctx.log.info("video: ready: %s (%dx%d)", video.title, video.width, video.height)
        self.ctx.invalidate()

    def _on_progress(self, fraction: float) -> None:
        self.progress = fraction

    # ---- scheduling ---------------------------------------------------------------------

    def should_display(self) -> bool:
        return True  # either the video, or a card that says what is missing or how far along it is

    def _status(self) -> tuple[str, str] | None:
        if not self.settings.url:
            return ("No video", "paste a link in settings")
        if self.progress is not None:
            return ("Downloading", f"{round(self.progress * 100)}%")
        if self.error is not None and not self.video.has_value:
            return ("Video failed", self.error.hint)
        if not self.video.has_value:
            return ("Video", "getting ready")
        if not find_binary("ffmpeg"):
            return ("No ffmpeg", "sudo apt install ffmpeg")
        if self._player is not None and self._player.error:
            return ("Can't play", "see the logs")
        return None

    def _playable_length(self, video: VideoFile) -> float | None:
        start, end = segment(video, self.settings)
        return (end - start) / self.settings.speed if end else None

    def duration(self) -> float:
        video = self.video.value
        if video is None or self._status() is not None:
            return STATUS_TURN_S
        length = self._playable_length(video)
        turn = float(self.settings.turn_seconds)
        if length is None:
            return turn or self.info.default_duration_s
        remaining = length
        if self.settings.resume and self._resume_at is not None:
            start, _ = segment(video, self.settings)
            remaining = max(1.0, length - (self._resume_at - start) / self.settings.speed)
        if turn:
            return turn if self.settings.loop else min(turn, remaining)
        return remaining

    def fps(self) -> int:
        return self.settings.fps if self._status() is None else 1

    def on_enter(self) -> None:
        self._labels.reset()
        self._clock = 0.0
        self._last = None
        self._start_player()

    def on_exit(self) -> None:
        if self._player is not None and self.settings.resume:
            # Finished without looping: next turn starts over rather than on the last frame.
            self._resume_at = None if self._player.finished else self._player.position()
        self._close_player()

    def _start_player(self, at: float | None = None) -> None:
        self._close_player()
        self._restart = False
        video = self.video.value
        if video is None or not find_binary("ffmpeg"):
            return
        start = segment(video, self.settings)[0]
        if at is not None:
            start = at
        elif self.settings.resume and self._resume_at is not None:
            start = self._resume_at
        self._player = Player(video, self.ctx.size, self.settings, start=start, log=self.ctx.log)

    def _close_player(self) -> None:
        player, self._player = self._player, None
        if player is not None:
            player.close()

    # ---- render -----------------------------------------------------------------------

    def render(self, canvas: Canvas, frame: FrameInfo) -> None:
        self._labels.advance(frame.dt)
        super().render(canvas, frame)

    @layout_fallback
    def render_any(self, c: Canvas, frame: FrameInfo) -> None:
        status = self._status()
        if status is not None:
            self._draw_status(c, status)
            return
        if self._restart or (self._player is None and self.video.has_value):
            # A setting changed mid-turn, or the download just finished. Adjusting the picture
            # carries on from the frame on the panel; a new video starts at its beginning.
            old = self._player
            same = old is not None and old.video == self.video.value
            self._start_player(at=old.position() if same and old is not None else None)
            self._clock = 0.0
        player = self._player
        if player is None:
            return
        self._clock += frame.dt
        data = player.take(self._clock)
        if data is not None:
            self._last = data
        if self._last is not None and len(self._last) == c.width * c.height * 3:
            c.blit(Image.frombytes("RGB", (c.width, c.height), self._last), 0, 0)
        else:
            c.clear()
        if self.settings.show_title and self._clock < TITLE_SECONDS:
            self._draw_title(c)

    def _draw_title(self, c: Canvas) -> None:
        video = self.video.value
        if video is None or not video.title:
            return
        font = get_font("4x6") if c.width >= 48 else get_font("tom-thumb")
        y = c.height - font.line_height - 1
        c.rect(0, y - 1, c.width, font.line_height + 2, fill=(0, 0, 0))
        self._labels.draw(c, 1, y, video.title, [font], c.width - 2, (255, 255, 255))

    def _draw_status(self, c: Canvas, status: tuple[str, str]) -> None:
        text = (255, 255, 255)
        draw_status_card(c, *status, text)
        if self.progress is not None and c.height >= 24:
            # A thin bar along the bottom, filling as the download goes.
            c.rect(2, c.height - 3, c.width - 4, 1, fill=dim(text, 0.2))
            c.rect(2, c.height - 3, round((c.width - 4) * self.progress), 1, fill=AMBER)
