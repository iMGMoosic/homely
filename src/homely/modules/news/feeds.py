"""Fetch and parse RSS/Atom feeds (feedparser does the parsing; httpx does the HTTP)."""

from __future__ import annotations

import asyncio
import calendar
import html
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import feedparser

from homely.data.http import ConditionalFetcher

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Headline:
    title: str
    link: str
    published: datetime | None
    source: str
    color: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat() if self.published else None
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Headline:
        pub = d.get("published")
        return cls(
            title=d["title"],
            link=d.get("link", ""),
            published=datetime.fromisoformat(pub) if pub else None,
            source=d.get("source", ""),
            color=d.get("color", "#00A8FF"),
        )


def clean_title(raw: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", raw or ""))
    return _WS.sub(" ", text).strip()


def _entry_time(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime.fromtimestamp(calendar.timegm(t), tz=UTC)
            except (OverflowError, ValueError):
                continue
    return None


def parse_feed(content: bytes | str, *, source_name: str, color: str) -> tuple[str, list[Headline]]:
    """Returns (feed title, headlines). ``source_name`` overrides the feed title when set."""
    parsed = feedparser.parse(content)
    feed_title = clean_title(parsed.feed.get("title", "")) or "News"
    name = source_name.strip() or feed_title
    out: list[Headline] = []
    for entry in parsed.entries:
        title = clean_title(entry.get("title", ""))
        if not title:
            continue
        out.append(
            Headline(title=title, link=entry.get("link", ""), published=_entry_time(entry), source=name, color=color)
        )
    return feed_title, out


class FeedFetcher(ConditionalFetcher):
    """Conditional GETs (so unchanged feeds cost almost nothing), parsed off the event loop."""

    async def fetch_and_parse(self, url: str, *, source_name: str, color: str) -> tuple[str, list[Headline]] | None:
        body = await self.fetch(url)
        if body is None:
            return None
        return await asyncio.to_thread(parse_feed, body, source_name=source_name, color=color)
