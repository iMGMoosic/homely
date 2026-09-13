"""Turn pydantic validation errors into one predictable 422 shape."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from homely.web.schemas import ApiError, ApiErrors


def to_api_errors(exc: ValidationError | RequestValidationError, strip_prefix: str = "") -> ApiErrors:
    errors: list[ApiError] = []
    for e in exc.errors():
        loc = [str(p) for p in e.get("loc", ())]
        if loc and loc[0] in ("body", "query", "path"):
            loc = loc[1:]
        path = ".".join(loc)
        if strip_prefix and path.startswith(strip_prefix):
            path = path[len(strip_prefix) :].lstrip(".")
        errors.append(ApiError(path=path, message=str(e.get("msg", "invalid")), type=str(e.get("type", "value_error"))))
    return ApiErrors(errors=errors)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _req(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=to_api_errors(exc).model_dump())

    @app.exception_handler(ValidationError)
    async def _pyd(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=to_api_errors(exc).model_dump())
