"""Status + event stream as JSON over a WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()

STATUS_INTERVAL_S = 2.0


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def event_to_json(event: object) -> dict[str, object]:
    data = dataclasses.asdict(event) if dataclasses.is_dataclass(event) and not isinstance(event, type) else {}
    return {"type": _snake(type(event).__name__), **data}


@router.websocket("/api/ws/events")
async def events_ws(ws: WebSocket) -> None:
    rt = ws.app.state.runtime
    await ws.accept()
    queue, unsub = rt.bus.subscribe_async()

    async def status_loop() -> None:
        while True:
            await ws.send_json({"type": "status", **rt.state().model_dump(), "restart_pending": rt.restart_pending})
            await asyncio.sleep(STATUS_INTERVAL_S)

    async def event_loop() -> None:
        while True:
            event = await queue.get()
            await ws.send_json(event_to_json(event))

    async def reader() -> None:
        while True:
            await ws.receive_text()

    tasks = [asyncio.create_task(status_loop()), asyncio.create_task(event_loop()), asyncio.create_task(reader())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect | RuntimeError):
                log.debug("events ws ended: %r", exc)
    finally:
        unsub()
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await t
