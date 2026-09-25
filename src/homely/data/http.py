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


class ConditionalFetcher:
    """Conditional GETs with ETag / Last-Modified so an unchanged feed costs almost nothing."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http
        self._validators: dict[str, dict[str, str]] = {}

    async def fetch(self, url: str) -> bytes | None:
        """Body bytes, or None when the server says the resource is unchanged (304)."""
        headers = dict(self._validators.get(url, {}))
        resp = await self._http.get(url, headers=headers, follow_redirects=True)
        if resp.status_code == 304:
            return None
        resp.raise_for_status()
        validators: dict[str, str] = {}
        if etag := resp.headers.get("etag"):
            validators["If-None-Match"] = etag
        if modified := resp.headers.get("last-modified"):
            validators["If-Modified-Since"] = modified
        self._validators[url] = validators
        return resp.content

    def forget(self, url: str) -> None:
        """Drop the validators so the next fetch returns the full body."""
        self._validators.pop(url, None)
