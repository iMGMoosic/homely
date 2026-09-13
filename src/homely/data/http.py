"""Shared async HTTP client."""

from __future__ import annotations

import httpx

from homely import __version__


def make_client(user_agent: str | None = None, timeout: float = 10.0) -> httpx.AsyncClient:
    ua = user_agent or f"homely/{__version__} (+https://github.com/imgmoosic/homely)"
    return httpx.AsyncClient(
        headers={"User-Agent": ua},
        timeout=httpx.Timeout(timeout),
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        follow_redirects=True,
    )
