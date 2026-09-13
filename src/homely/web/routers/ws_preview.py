"""Live preview: binary frames over a WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from homely.display.framebus import ENC_PNG, ENC_RGB

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/api/ws/preview")
async def preview_ws(ws: WebSocket, fps: int = Query(20, ge=1, le=30), fmt: str = Query("png")) -> None:
    rt = ws.app.state.runtime
    if rt.auth_required():
        # Browsers send cached Basic credentials on the upgrade request.
        from base64 import b64decode

        header = ws.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            with contextlib.suppress(Exception):
                user, _, pw = b64decode(header[6:]).decode().partition(":")
                ok = user == "homely" and rt.check_password(pw)
        if not ok:
            await ws.close(code=4401)
            return
    await ws.accept()
    encoding = ENC_RGB if fmt == "rgb" else ENC_PNG
    sub = rt.framebus.subscribe()
    rate = {"fps": fps}

    async def reader() -> None:
        try:
            while True:
                msg = await ws.receive_text()
                with contextlib.suppress(Exception):
                    data = json.loads(msg)
                    if data.get("type") == "fps":
                        rate["fps"] = max(1, min(30, int(data.get("value", fps))))
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    reader_task = asyncio.create_task(reader())
    last_seq = -1
    try:
        while not reader_task.done():
            pkt = await sub.wait_for_new(last_seq, timeout=5.0)
            if pkt is None:
                continue
            await ws.send_bytes(rt.framebus.encoded(pkt, encoding))
            last_seq = pkt.seq
            await asyncio.sleep(1.0 / rate["fps"])
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sub.close()
        reader_task.cancel()
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await reader_task
