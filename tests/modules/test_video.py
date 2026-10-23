from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

from homely.core.module import FrameInfo
from homely.modules.video import fetch
from homely.modules.video.fetch import Downloader, VideoError, VideoFile
from homely.modules.video.module import VideoModule
from homely.modules.video.player import Player, crop_box, filter_chain, fitted, segment
from homely.modules.video.settings import VideoSettings
from homely.render.canvas import Canvas
from homely.render.size import SUPPORTED_SIZES, Size
from tests.conftest import FROZEN, make_ctx
from tests.golden_util import assert_golden

WIDE = Size(128, 32)


def _ffmpeg_on_path() -> None:
    """Without a system ffmpeg, use the static one from the imageio-ffmpeg wheel (a dev dependency).

    CI takes this route: apt mirrors on the hosted runners hang often enough to fail builds.
    """
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
    except ImportError:
        return
    import os
    import tempfile

    bindir = Path(tempfile.mkdtemp(prefix="homely-ffmpeg-"))
    (bindir / "ffmpeg").symlink_to(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


_ffmpeg_on_path()
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def vf(width: int = 640, height: int = 360, duration: float | None = 10.0, path: str = "/x.mp4") -> VideoFile:
    return VideoFile("https://youtu.be/x", 360, path, "A test video", width, height, duration)


# ---- settings and picture math -------------------------------------------------------------


def test_settings_validation():
    with pytest.raises(ValidationError):
        VideoSettings(url="youtube.com/watch?v=x")
    with pytest.raises(ValidationError):
        VideoSettings(start_at=20, end_at=10)
    assert VideoSettings(url="  https://youtu.be/x ").url == "https://youtu.be/x"
    assert VideoSettings(start_at=5, end_at=0).end_at == 0  # 0 = to the end


def test_fill_crops_to_the_panel_shape_and_focus_moves_it():
    s = VideoSettings()
    box = crop_box(640, 360, WIDE, s)
    assert (box.w, box.h) == (640, 160) and (box.x, box.y) == (0, 100)  # a 4:1 band through the middle
    top = crop_box(640, 360, WIDE, VideoSettings(focus_y=0))
    bottom = crop_box(640, 360, WIDE, VideoSettings(focus_y=100))
    assert top.y == 0 and bottom.y == 200
    tall = crop_box(640, 360, Size(32, 128), VideoSettings(focus_x=100))
    assert (tall.w, tall.h) == (90, 360) and tall.x == 550


def test_zoom_and_fit():
    zoomed = crop_box(640, 360, WIDE, VideoSettings(zoom=200, focus_x=0))
    assert (zoomed.w, zoomed.h, zoomed.x) == (320, 80, 0)
    whole = crop_box(640, 360, WIDE, VideoSettings(fit="fit"))
    assert (whole.w, whole.h, whole.x, whole.y) == (640, 360, 0, 0)
    assert fitted(whole, WIDE) == (57, 32)  # letterboxed into the middle of the panel


def test_filter_chain():
    plain = filter_chain(vf(), WIDE, VideoSettings())
    assert plain == "crop=640:160:0:100,scale=128:32:flags=area,setsar=1,fps=30"
    fancy = filter_chain(
        vf(),
        WIDE,
        VideoSettings(fit="fit", speed=2, mirror=True, scaling="pixel", saturation=150, fps=20),
    )
    assert fancy.startswith("setpts=PTS/2,scale=57:32:flags=neighbor,pad=128:32:35:0:black")
    assert "hflip" in fancy and "eq=brightness=0:contrast=1:saturation=1.5" in fancy and fancy.endswith("fps=20")
    assert "scale=128:32" in filter_chain(vf(), WIDE, VideoSettings(fit="stretch"))


def test_segment_clamps_to_the_video():
    assert segment(vf(duration=10), VideoSettings()) == (0.0, 10.0)
    assert segment(vf(duration=10), VideoSettings(start_at=2, end_at=50)) == (2.0, 10.0)
    assert segment(vf(duration=10), VideoSettings(start_at=30)) == (9.5, 10.0)
    assert segment(vf(duration=None), VideoSettings(start_at=3)) == (3.0, None)


# ---- downloading -----------------------------------------------------------------------------


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: writes a file where the real one would."""

    fail: str | None = None

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download):
        if FakeYDL.fail:
            raise FakeDownloadError(FakeYDL.fail)
        for hook in self.opts["progress_hooks"]:
            hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})
            hook({"status": "finished"})
        info = {"id": "abc", "height": 240, "width": 426, "duration": 12, "title": "  Big   Buck ", "ext": "mp4"}
        Path(self.prepare_filename(info)).write_bytes(b"video")
        return info

    def prepare_filename(self, info):
        return (
            self.opts["outtmpl"]
            .replace("%(id)s", info["id"])
            .replace("%(height)s", "240")
            .replace("%(ext)s", info["ext"])
        )


class FakeDownloadError(Exception):
    pass


@pytest.fixture
def fake_ytdlp(monkeypatch):
    mod = types.ModuleType("yt_dlp")
    mod.YoutubeDL = FakeYDL  # type: ignore[attr-defined]
    mod.utils = types.SimpleNamespace(DownloadError=FakeDownloadError)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yt_dlp", mod)
    FakeYDL.fail = None
    return FakeYDL


def test_download_writes_metadata_and_replaces_the_old_video(tmp_path, fake_ytdlp):
    d = Downloader(tmp_path / "video", __import__("logging").getLogger("t"))
    (tmp_path / "video").mkdir()
    (tmp_path / "video" / "old-360p.mp4").write_bytes(b"old")
    seen: list[float] = []
    video = d.download("https://youtu.be/abc", 240, seen.append)
    assert video.title == "Big Buck" and (video.width, video.height, video.duration) == (426, 240, 12.0)
    assert seen == [0.5, 1.0]
    assert not (tmp_path / "video" / "old-360p.mp4").exists()
    assert d.cached("https://youtu.be/abc", 240) == video
    assert d.cached("https://youtu.be/abc", 360) is None  # different quality: download again
    assert json.loads((tmp_path / "video" / "video.json").read_text())["path"] == video.path


@pytest.mark.parametrize(
    ("message", "hint"),
    [
        ("ERROR: [youtube] x: Video unavailable", "video unavailable"),
        ("ERROR: Sign in to confirm your age", "needs a sign-in"),
        ("ERROR: Unsupported URL: https://example.com", "not a video link"),
        ("ERROR: Unable to download webpage: timed out", "check the network"),
        ("ERROR: something new and strange", "try homely upgrade"),
    ],
)
def test_download_errors_become_hints(tmp_path, fake_ytdlp, message, hint):
    fake_ytdlp.fail = message
    with pytest.raises(VideoError) as err:
        Downloader(tmp_path, __import__("logging").getLogger("t")).download("https://youtu.be/x", 240, lambda f: None)
    assert err.value.hint == hint


# ---- playback ----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def red_then_blue(tmp_path_factory) -> VideoFile:
    """A 2 s, 160x90 clip: red for the first second, blue for the second."""
    path = tmp_path_factory.mktemp("clip") / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=160x90:r=30:d=1",
         "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=30:d=1",
         "-filter_complex", "[0][1]concat=n=2:v=1", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )  # fmt: skip
    return VideoFile("https://youtu.be/rb", 360, str(path), "Red then blue", 160, 90, 2.0)


def _wait_for(player: Player, t: float) -> bytes:
    deadline = time.monotonic() + 10
    frame = None
    while frame is None and time.monotonic() < deadline:
        frame = player.take(t)
        time.sleep(0.01)
    assert frame is not None, player.error
    return frame


def _color(frame: bytes, size: Size) -> tuple[int, int, int]:
    mid = (size.h // 2 * size.w + size.w // 2) * 3
    return frame[mid], frame[mid + 1], frame[mid + 2]


@needs_ffmpeg
def test_player_plays_loops_and_reports_position(red_then_blue):
    log = __import__("logging").getLogger("t")
    p = Player(red_then_blue, WIDE, VideoSettings(fps=10), start=0.0, log=log)
    try:
        first = _wait_for(p, 0.0)
        assert len(first) == 128 * 32 * 3
        r, _, b = _color(first, WIDE)
        assert r > 200 and b < 60
        late = _wait_for(p, 1.5)
        assert _color(late, WIDE)[2] > 200  # blue half
        assert 1.3 <= p.position() <= 1.6
        # Past the end: looping starts over in red. Wait for the second pass to be decoded.
        deadline = time.monotonic() + 10
        looped = late
        while p.position() >= 1.0 and time.monotonic() < deadline:
            looped = p.take(2.2) or looped
            time.sleep(0.01)
        assert p.position() < 1.0 and _color(looped, WIDE)[0] > 200 and not p.finished
    finally:
        p.close()


@needs_ffmpeg
def test_player_without_loop_finishes_and_honours_start(red_then_blue):
    log = __import__("logging").getLogger("t")
    p = Player(red_then_blue, WIDE, VideoSettings(fps=10, loop=False), start=1.2, log=log)
    try:
        assert _color(_wait_for(p, 0.0), WIDE)[2] > 200  # started in the blue half
        deadline = time.monotonic() + 10
        while not p.finished and time.monotonic() < deadline:
            p.take(10.0)
            time.sleep(0.01)
        assert p.finished
    finally:
        p.close()


@needs_ffmpeg
def test_player_reports_a_broken_file(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    p = Player(
        VideoFile("u", 360, str(bad), "", 160, 90, 2.0),
        WIDE,
        VideoSettings(),
        start=0,
        log=__import__("logging").getLogger("t"),
    )
    try:
        deadline = time.monotonic() + 10
        while not p.ended and time.monotonic() < deadline:
            time.sleep(0.02)
        assert p.ended and p.error
    finally:
        p.close()


# ---- the module --------------------------------------------------------------------------------


def frame(i: int = 0, dt: float = 1 / 30) -> FrameInfo:
    return FrameInfo(now=FROZEN, monotonic=0, dt=dt, index=i, slot_elapsed=i * dt, slot_duration=30)


def test_turn_length_follows_loop_turn_and_resume():
    mod = VideoModule(make_ctx(WIDE), VideoSettings(url="https://youtu.be/x"))
    assert mod.duration() == 10.0  # no video yet: a short status turn
    mod.video.set(vf(duration=40), FROZEN)
    mod.settings = VideoSettings(url="https://youtu.be/x", start_at=10)
    assert mod.duration() == 30.0  # one play-through of 10..40
    mod.settings = VideoSettings(url="https://youtu.be/x", speed=2)
    assert mod.duration() == 20.0
    mod.settings = VideoSettings(url="https://youtu.be/x", turn_seconds=90)
    assert mod.duration() == 90.0  # loops to fill the turn
    mod.settings = VideoSettings(url="https://youtu.be/x", turn_seconds=90, loop=False)
    assert mod.duration() == 40.0  # ends with the video
    mod.settings = VideoSettings(url="https://youtu.be/x", resume=True)
    mod._resume_at = 25.0
    assert mod.duration() == 15.0  # the rest of the video


def test_status_cards():
    mod = VideoModule(make_ctx(WIDE), VideoSettings())
    assert mod._status() == ("No video", "paste a link in settings") and mod.fps() == 1
    mod.settings = VideoSettings(url="https://youtu.be/x")
    mod.progress = 0.42
    assert mod._status() == ("Downloading", "42%")
    mod.progress = None
    mod.error = VideoError("boom", "video unavailable")
    assert mod._status() == ("Video failed", "video unavailable")
    assert mod.should_display()


def test_golden_downloading_card(request):
    mod = VideoModule(make_ctx(WIDE), VideoSettings(url="https://youtu.be/x"))
    mod.progress = 0.42
    c = Canvas(WIDE)
    mod.render(c, frame())
    assert_golden(c.snapshot(), "video/128x32/downloading", request)


@needs_ffmpeg
@pytest.mark.parametrize("size", SUPPORTED_SIZES, ids=str)
def test_module_plays_the_video_at_every_size(size, red_then_blue, tmp_path):
    mod = VideoModule(make_ctx(size, tmp=tmp_path), VideoSettings(url=red_then_blue.url, fps=10, show_title=True))
    mod.video.set(red_then_blue, FROZEN)
    mod.on_enter()
    try:
        c = Canvas(size)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            mod.render(c, frame(dt=0))
            if mod._last is not None:
                break
            time.sleep(0.01)
        img = c.snapshot()
        pixel = img.getpixel((size.w // 2, size.h // 4))
        assert pixel[0] > 200 and pixel[2] < 60, (size, pixel)
        assert img.getpixel((size.w // 2, size.h - 2)) != pixel  # the title strip is drawn over it
    finally:
        mod.on_exit()
    assert mod._player is None


@needs_ffmpeg
def test_resume_picks_up_where_it_left_off(red_then_blue, tmp_path):
    mod = VideoModule(make_ctx(WIDE, tmp=tmp_path), VideoSettings(url=red_then_blue.url, fps=10, resume=True))
    mod.video.set(red_then_blue, FROZEN)
    mod.on_enter()
    try:
        deadline = time.monotonic() + 10
        c = Canvas(WIDE)
        mod.render(c, frame(dt=1.4))
        while mod._player is not None and mod._player.position() < 1.3 and time.monotonic() < deadline:
            mod.render(c, frame(dt=0))
            time.sleep(0.01)
    finally:
        mod.on_exit()
    assert mod._resume_at is not None and 1.3 <= mod._resume_at <= 1.5
    assert mod.duration() == pytest.approx(max(1.0, 2.0 - mod._resume_at))  # at least a second


def test_js_runtime_detection(monkeypatch):
    monkeypatch.setattr(fetch, "find_binary", lambda name: f"/usr/bin/{name}" if name in ("deno", "node") else None)
    assert fetch.js_runtimes() == {"deno": {"path": "/usr/bin/deno"}, "node": {"path": "/usr/bin/node"}}


@needs_ffmpeg
def test_changing_the_picture_mid_turn_carries_on_from_the_same_frame(red_then_blue, tmp_path):
    import asyncio

    settings = VideoSettings(url=red_then_blue.url, fps=10)
    mod = VideoModule(make_ctx(WIDE, tmp=tmp_path), settings)
    mod.video.set(red_then_blue, FROZEN)
    mod.on_enter()
    try:
        c = Canvas(WIDE)
        mod.render(c, frame(dt=1.4))
        deadline = time.monotonic() + 10
        while mod._player is not None and mod._player.position() < 1.3 and time.monotonic() < deadline:
            mod.render(c, frame(dt=0))
            time.sleep(0.01)
        asyncio.run(mod.on_settings_changed(settings.model_copy(update={"saturation": 50})))
        mod.render(c, frame(dt=0))
        assert mod._player is not None and mod._player.position() >= 1.3  # not back at the start
    finally:
        mod.on_exit()


@pytest.mark.skipif(sys.platform == "win32" or __import__("os").geteuid() == 0, reason="root reads anything")
def test_find_binary_skips_directories_it_cannot_read(tmp_path, monkeypatch):
    # On the Pi homely starts as root (HOME=/root) and drops to the homely user, which cannot read
    # /root: looking for ~/.deno/bin/node there used to raise PermissionError and fail the download.
    locked = tmp_path / "root"
    (locked / ".deno" / "bin").mkdir(parents=True)
    usable = tmp_path / "bin"
    usable.mkdir()
    deno = usable / "deno"
    deno.write_text("#!/bin/sh\n")
    deno.chmod(0o755)
    locked.chmod(0o000)
    try:
        monkeypatch.setattr(fetch, "extra_bin_dirs", lambda: [locked / ".deno" / "bin", usable])
        monkeypatch.setattr(fetch.shutil, "which", lambda name: None)
        assert fetch.find_binary("node") is None
        assert fetch.find_binary("deno") == str(deno)
        assert fetch.js_runtimes() == {"deno": {"path": str(deno)}}
    finally:
        locked.chmod(0o755)


def test_extra_bin_dirs_use_the_running_users_home_not_HOME(monkeypatch):
    import pwd

    monkeypatch.setenv("HOME", "/root")
    home = pwd.getpwuid(__import__("os").geteuid()).pw_dir
    assert fetch.extra_bin_dirs() == [fetch.INSTALL_BIN_DIR, Path(home) / ".deno" / "bin"]
