from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from homely.core.module import ModuleSettings


class FeedSource(BaseModel):
    name: str = Field("", title="Name", description="Shown above headlines; empty uses the feed's own title")
    url: str = Field(title="Feed URL", description="RSS or Atom")
    color: str = Field("#00A8FF", title="Color", pattern=r"^#[0-9A-Fa-f]{6}$", json_schema_extra={"format": "color"})

    @field_validator("url")
    @classmethod
    def _http(cls, v: str) -> str:
        v = v.strip()
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return v


DEFAULT_FEEDS = [
    FeedSource(name="BBC World", url="https://feeds.bbci.co.uk/news/world/rss.xml", color="#BB1919"),
    FeedSource(name="NPR", url="https://feeds.npr.org/1001/rss.xml", color="#6CA6E0"),
    FeedSource(name="Hacker News", url="https://hnrss.org/frontpage", color="#FF6600"),
]


class NewsSettings(ModuleSettings):
    feeds: list[FeedSource] = Field(
        default_factory=lambda: list(DEFAULT_FEEDS),
        title="Feeds",
        json_schema_extra={"x-group": "Feeds", "x-order": 10},
    )
    refresh_minutes: int = Field(
        15, ge=5, le=180, title="Refresh every (minutes)", json_schema_extra={"x-group": "Feeds", "x-order": 20}
    )
    max_age_hours: int = Field(
        36, ge=1, le=168, title="Ignore items older than (hours)", json_schema_extra={"x-group": "Feeds", "x-order": 30}
    )
    mix: Literal["interleave", "newest"] = Field(
        "interleave",
        title="Order",
        description="interleave = take turns between feeds; newest = strictly by time",
        json_schema_extra={"x-group": "Feeds", "x-order": 40},
    )
    headlines_per_slot: int = Field(
        3, ge=1, le=10, title="Headlines per turn", json_schema_extra={"x-group": "Layout", "x-order": 10}
    )
    seconds_per_headline: int = Field(
        10, ge=3, le=60, title="Seconds per headline", json_schema_extra={"x-group": "Layout", "x-order": 20}
    )
    show_age: bool = Field(
        True, title="Show how old the item is", json_schema_extra={"x-group": "Layout", "x-order": 30}
    )
    text_color: str = Field(
        "#FFFFFF",
        title="Headline color",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        json_schema_extra={"x-group": "Layout", "x-order": 40, "format": "color"},
    )
