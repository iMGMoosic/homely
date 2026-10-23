"""Download a video once with yt-dlp and keep it next to a small metadata file.

YouTube now makes clients solve a JavaScript challenge before it hands out most formats.
yt-dlp's ``default`` extra ships the solver script; it still needs a JavaScript runtime on the
machine (Deno is its default; Node 22+, Bun and QuickJS also work). Without one yt-dlp falls back
to whatever formats need no challenge, which is often still enough for a low-resolution file.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

META = "video.json"
# H.264 first: it is the cheapest codec to decode on a Pi 4 (VP9 and AV1 are software-only and
# much heavier). Video only -- the board has no speaker -- unless a site only offers muxed files.
FORMAT = "bv*[height<={h}][vcodec^=avc1]/bv*[height<={h}]/b[height<={h}]/wv*/w"
JS_RUNTIMES = ("deno", "node", "bun", "quickjs")
EXTRA_BIN_DIRS = (Path("/opt/homely/bin"), Path.home() / ".deno" / "bin")


class VideoError(Exception):
    """A download failed for a reason worth showing on the panel."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.hint = hint


@dataclass(frozen=True)
class VideoFile:
    url: str
    max_height: int
    path: str
    title: str
    width: int
    height: int
    duration: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VideoFile:
        return cls(
            url=str(d["url"]),
            max_height=int(d["max_height"]),
            path=str(d["path"]),
            title=str(d.get("title", "")),
            width=int(d["width"]),
            height=int(d["height"]),
            duration=float(d["duration"]) if d.get("duration") else None,
        )


def find_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for d in EXTRA_BIN_DIRS:
        p = d / name
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def js_runtimes() -> dict[str, dict[str, str]]:
    """Every JS runtime yt-dlp knows about that is installed here (yt-dlp checks the versions)."""
    out: dict[str, dict[str, str]] = {}
    for name in JS_RUNTIMES:
        path = find_binary(name)
        if path:
            out[name] = {"path": path}
    return out


class _Logger:
    """yt-dlp talks through a logger object; route it into ours, minus the progress chatter."""

    def __init__(self, log: logging.Logger) -> None:
        self.log = log

    def debug(self, msg: str) -> None:
        if not msg.startswith("[download]"):
            self.log.debug("yt-dlp: %s", msg)

    def info(self, msg: str) -> None:
        self.log.debug("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        self.log.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        self.log.error("yt-dlp: %s", msg)


class Downloader:
    def __init__(self, directory: Path, log: logging.Logger) -> None:
        self.directory = directory
        self.log = log

    def cached(self, url: str, max_height: int) -> VideoFile | None:
        try:
            video = VideoFile.from_dict(json.loads((self.directory / META).read_text()))
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if video.url != url or video.max_height != max_height or not Path(video.path).is_file():
            return None
        return video

    def download(self, url: str, max_height: int, progress: Callable[[float], None]) -> VideoFile:
        """Blocking: run it in a thread. Replaces whatever video this instance had before."""
        import yt_dlp  # imported here: it is a large import, and only this module needs it

        self.directory.mkdir(parents=True, exist_ok=True)
        # Deno keeps a cache of the solver script; under systemd HOME is not writable.
        os.environ.setdefault("DENO_DIR", str(self.directory.parent / ".deno"))

        def hook(d: dict[str, Any]) -> None:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    progress(min(1.0, float(d.get("downloaded_bytes") or 0) / float(total)))
            elif d.get("status") == "finished":
                progress(1.0)

        opts: dict[str, Any] = {
            "format": FORMAT.format(h=max_height),
            "outtmpl": str(self.directory / "%(id)s-%(height)sp.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "noprogress": True,
            "logger": _Logger(self.log),
            "progress_hooks": [hook],
            "cachedir": str(self.directory.parent / ".yt-dlp-cache"),
            "js_runtimes": js_runtimes(),
            "overwrites": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise VideoError("nothing to download", "check the link")
                if info.get("_type") == "playlist":
                    entries = [e for e in info.get("entries") or [] if e]
                    if not entries:
                        raise VideoError("empty playlist", "link a single video")
                    info = entries[0]
                path = Path(ydl.prepare_filename(info))
        except yt_dlp.utils.DownloadError as exc:
            raise _explain(str(exc)) from exc
        if not path.is_file():
            raise VideoError(f"yt-dlp reported success but {path.name} is missing", "try again")
        width, height = int(info.get("width") or 0), int(info.get("height") or 0)
        duration = info.get("duration")
        if not width or not height or not duration:
            width, height, duration = probe(path, width, height, duration)
        video = VideoFile(
            url=url,
            max_height=max_height,
            path=str(path),
            title=" ".join(str(info.get("title") or "").split()),
            width=width,
            height=height,
            duration=float(duration) if duration else None,
        )
        (self.directory / META).write_text(json.dumps(video.to_dict()))
        for old in self.directory.iterdir():  # only the current video is kept
            if old.is_file() and old.name != META and old != path:
                old.unlink(missing_ok=True)
        return video


def probe(path: Path, width: int, height: int, duration: Any) -> tuple[int, int, float | None]:
    """Fill in whatever yt-dlp did not report, from the file itself."""
    import subprocess

    ffprobe = find_binary("ffprobe")
    if not ffprobe:
        return width or 16, height or 9, duration
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30,
    ).stdout  # fmt: skip
    try:
        data = json.loads(out)
        stream = (data.get("streams") or [{}])[0]
        width = width or int(stream.get("width") or 0)
        height = height or int(stream.get("height") or 0)
        duration = duration or float((data.get("format") or {}).get("duration") or 0) or None
    except (ValueError, TypeError):
        pass
    return width or 16, height or 9, duration


def _explain(message: str) -> VideoError:
    low = message.lower()
    if "private" in low or "unavailable" in low or "removed" in low or "does not exist" in low:
        return VideoError(message, "video unavailable")
    if "sign in" in low or ("age" in low and "confirm" in low):
        return VideoError(message, "needs a sign-in")
    if "unsupported url" in low:
        return VideoError(message, "not a video link")
    if "unable to download" in low or "timed out" in low or "network" in low or "resolve" in low:
        return VideoError(message, "check the network")
    return VideoError(message, "try homely upgrade")
