"""FastAPI dependencies."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

if TYPE_CHECKING:
    from homely.app import Runtime

_basic = HTTPBasic(auto_error=False)


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime  # type: ignore[no-any-return]


Rt = Annotated["Runtime", Depends(get_runtime)]


async def require_auth(request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)]) -> None:
    rt: Runtime = request.app.state.runtime
    if not rt.auth_required():
        return
    ok = (
        credentials is not None
        and secrets.compare_digest(credentials.username, "homely")
        and rt.check_password(credentials.password)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Basic realm=homely"},
        )
