"""Place search for the location picker, proxied to Open-Meteo's geocoding API (no key needed)."""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from homely.web import schemas
from homely.web.deps import Rt, require_auth

router = APIRouter(prefix="/api", tags=["geocode"], dependencies=[Depends(require_auth)])

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_CACHE_TTL = 3600.0
_cache: dict[str, tuple[float, list[schemas.GeocodeResult]]] = {}


def parse_results(data: dict[str, Any]) -> list[schemas.GeocodeResult]:
    out: list[schemas.GeocodeResult] = []
    for r in data.get("results") or []:
        parts = [p for p in (r.get("name"), r.get("admin1"), r.get("country")) if p]
        out.append(
            schemas.GeocodeResult(
                name=r.get("name", ""),
                admin1=r.get("admin1"),
                country=r.get("country"),
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                timezone=r.get("timezone"),
                label=", ".join(dict.fromkeys(parts)),
            )
        )
    return out


@router.get("/geocode", response_model=list[schemas.GeocodeResult])
async def geocode(
    rt: Rt, q: str = Query(min_length=2, max_length=80), count: int = Query(8, ge=1, le=20)
) -> list[schemas.GeocodeResult]:
    key = f"{q.strip().lower()}|{count}"
    hit = _cache.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    if rt.http is None:
        raise HTTPException(503, "http client not ready")
    try:
        resp = await rt.http.get(
            GEOCODE_URL, params={"name": q.strip(), "count": str(count), "language": "en", "format": "json"}
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"geocoding failed: {exc}") from exc
    results = parse_results(resp.json())
    _cache[key] = (now, results)
    return results
