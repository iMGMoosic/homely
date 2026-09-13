from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from homely import __version__
from homely.web import schemas
from homely.web.deps import Rt, require_auth

router = APIRouter(prefix="/api", tags=["system"])

Action = Literal["restart-renderer", "test-pattern", "reload-config", "next", "prev", "reboot", "shutdown"]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/system", response_model=schemas.SystemInfo, dependencies=[Depends(require_auth)])
async def system(rt: Rt) -> schemas.SystemInfo:
    return rt.system_info()


@router.get("/state", response_model=schemas.StateInfo, dependencies=[Depends(require_auth)])
async def state(rt: Rt) -> schemas.StateInfo:
    return rt.state()


@router.get("/logs", response_model=list[schemas.LogLine], dependencies=[Depends(require_auth)])
async def logs(
    limit: int = Query(200, ge=1, le=500),
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Query("INFO"),
) -> list[schemas.LogLine]:
    from homely.system import logbuffer

    handler = logbuffer.install()
    return [schemas.LogLine(**ln) for ln in handler.tail(limit, level)]


@router.post("/system/actions/{action}", response_model=schemas.ActionResult, dependencies=[Depends(require_auth)])
async def run_action(action: Action, rt: Rt) -> schemas.ActionResult:
    try:
        return await rt.run_action(action)
    except KeyError:
        raise HTTPException(404, f"unknown action {action!r}") from None
