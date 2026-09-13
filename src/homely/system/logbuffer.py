"""Keep the last few hundred log lines in memory so the web UI can show them."""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


class RingBufferHandler(logging.Handler):
    def __init__(self, maxlen: int = 500) -> None:
        super().__init__(level=logging.DEBUG)
        self._lines: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                msg += f" ({record.exc_info[0].__name__ if record.exc_info[0] else 'error'}: {record.exc_info[1]})"
            line = {
                "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
            }
        except Exception:  # never let logging break the app
            return
        with self._lock:
            self._lines.append(line)

    def tail(self, limit: int = 200, min_level: str = "DEBUG") -> list[dict[str, Any]]:
        threshold = _LEVELS.get(min_level.upper(), 10)
        with self._lock:
            lines = [ln for ln in self._lines if _LEVELS.get(ln["level"], 0) >= threshold]
        return lines[-limit:]


_handler: RingBufferHandler | None = None


def install(maxlen: int = 500) -> RingBufferHandler:
    """Attach the buffer to the root logger once and return it."""
    global _handler
    if _handler is None:
        _handler = RingBufferHandler(maxlen)
        logging.getLogger().addHandler(_handler)
    return _handler


def get() -> RingBufferHandler | None:
    return _handler
