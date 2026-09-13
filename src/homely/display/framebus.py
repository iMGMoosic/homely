"""FrameBus: latest-frame mailbox from the render thread to asyncio subscribers.

Only the newest frame is kept. Each subscriber has its own asyncio.Event, so a slow
websocket client never blocks the render thread or other clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import struct
import threading
from dataclasses import dataclass

from PIL import Image

from homely.render.size import Size

HEADER = struct.Struct(">BBHHIB")  # version, encoding, w, h, seq, brightness
VERSION = 1
ENC_PNG = 0
ENC_RGB = 1


@dataclass(frozen=True)
class FramePacket:
    seq: int
    image: Image.Image
    brightness: int

    @property
    def size(self) -> Size:
        return Size(self.image.width, self.image.height)


def encode_packet(packet: FramePacket, encoding: int = ENC_PNG) -> bytes:
    header = HEADER.pack(
        VERSION, encoding, packet.image.width, packet.image.height, packet.seq & 0xFFFFFFFF, packet.brightness
    )
    if encoding == ENC_RGB:
        return header + packet.image.tobytes()
    buf = io.BytesIO()
    packet.image.save(buf, format="PNG", compress_level=1)
    return header + buf.getvalue()


class FrameSubscription:
    def __init__(self, bus: FrameBus, loop: asyncio.AbstractEventLoop) -> None:
        self._bus = bus
        self._loop = loop
        self._event = asyncio.Event()
        self.closed = False

    def _notify(self) -> None:
        if not self.closed:
            self._event.set()

    async def wait_for_new(self, last_seq: int, timeout: float | None = None) -> FramePacket | None:
        """Wait for a packet with seq != last_seq. Returns None on timeout."""
        while True:
            packet = self._bus.latest()
            if packet is not None and packet.seq != last_seq:
                return packet
            self._event.clear()
            try:
                await asyncio.wait_for(self._event.wait(), timeout)
            except TimeoutError:
                return None

    def close(self) -> None:
        self.closed = True
        self._bus._unsubscribe(self)


class FrameBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: FramePacket | None = None
        self._seq = 0
        self._subs: list[FrameSubscription] = []
        self._encoded: dict[tuple[int, int], bytes] = {}
        self.brightness = 100

    # ---- render thread ----------------------------------------------------------

    def publish(self, frame: Image.Image) -> None:
        with self._lock:
            self._seq += 1
            self._latest = FramePacket(seq=self._seq, image=frame.copy(), brightness=self.brightness)
            self._encoded.clear()
            subs = list(self._subs)
        for sub in subs:
            with contextlib.suppress(RuntimeError):  # loop closed
                sub._loop.call_soon_threadsafe(sub._notify)

    def set_brightness(self, level: int) -> None:
        self.brightness = level

    # ---- asyncio side -----------------------------------------------------------

    def latest(self) -> FramePacket | None:
        return self._latest

    @property
    def has_subscribers(self) -> bool:
        return bool(self._subs)

    def subscribe(self, loop: asyncio.AbstractEventLoop | None = None) -> FrameSubscription:
        loop = loop or asyncio.get_running_loop()
        sub = FrameSubscription(self, loop)
        with self._lock:
            self._subs.append(sub)
        return sub

    def _unsubscribe(self, sub: FrameSubscription) -> None:
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)

    def encoded(self, packet: FramePacket, encoding: int = ENC_PNG) -> bytes:
        """Encode once per (seq, encoding) and share across clients."""
        key = (packet.seq, encoding)
        with self._lock:
            cached = self._encoded.get(key)
        if cached is not None:
            return cached
        data = encode_packet(packet, encoding)
        with self._lock:
            if self._latest is not None and self._latest.seq == packet.seq:
                self._encoded[key] = data
        return data
