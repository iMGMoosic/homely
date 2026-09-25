"""Stop picker for the Transit module: route -> direction -> stop -> stop number."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from homely.modules.transit.providers import PROVIDERS, Choice, TransitError, TransitProvider
from homely.web import schemas
from homely.web.deps import Rt, require_auth

router = APIRouter(prefix="/api/transit", tags=["transit"], dependencies=[Depends(require_auth)])

_CACHE_TTL = 3600.0
_cache: dict[str, tuple[float, list[Choice]]] = {}
# One Annotated alias rather than one shared Query() default: FastAPI binds a shared default
# instance to a single parameter name, so route and direction would both read ?route=.
Id = Annotated[str, Query(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")]


def _provider(rt: Rt, name: str) -> TransitProvider:
    if name not in PROVIDERS:
        raise HTTPException(404, f"unknown transit provider {name!r}")
    if rt.http is None:
        raise HTTPException(503, "http client not ready")
    return PROVIDERS[name](rt.http)


async def _cached(key: str, fetch: Callable[[], Awaitable[list[Choice]]]) -> list[schemas.TransitChoice]:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is None or now - hit[0] >= _CACHE_TTL:
        try:
            hit = (now, await fetch())
        except TransitError as exc:
            raise HTTPException(404, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"transit lookup failed: {exc}") from exc
        _cache[key] = hit
    return [schemas.TransitChoice(id=c.id, label=c.label) for c in hit[1]]


@router.get("/{provider}/routes", response_model=list[schemas.TransitChoice])
async def routes(rt: Rt, provider: str) -> list[schemas.TransitChoice]:
    p = _provider(rt, provider)
    return await _cached(f"{provider}|routes", p.routes)


@router.get("/{provider}/directions", response_model=list[schemas.TransitChoice])
async def directions(rt: Rt, provider: str, route: Id) -> list[schemas.TransitChoice]:
    p = _provider(rt, provider)
    return await _cached(f"{provider}|dir|{route}", lambda: p.directions(route))


@router.get("/{provider}/stops", response_model=list[schemas.TransitChoice])
async def stops(rt: Rt, provider: str, route: Id, direction: Id) -> list[schemas.TransitChoice]:
    p = _provider(rt, provider)
    return await _cached(f"{provider}|stops|{route}|{direction}", lambda: p.stops(route, direction))


@router.get("/{provider}/stop", response_model=schemas.TransitChoice)
async def resolve(rt: Rt, provider: str, route: Id, direction: Id, place: Id) -> schemas.TransitChoice:
    """The stop number for a place picked from the list (not cached: it is looked up once)."""
    p = _provider(rt, provider)
    try:
        c = await p.resolve_stop(route, direction, place)
    except TransitError as exc:
        raise HTTPException(404, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"transit lookup failed: {exc}") from exc
    return schemas.TransitChoice(id=c.id, label=c.label)
