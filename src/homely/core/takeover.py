"""Takeover stack: a module (game, alert) can grab the whole screen out of rotation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Takeover:
    instance_id: str
    priority: int = 10
    expires_at: float | None = None  # monotonic seconds


class TakeoverStack:
    def __init__(self) -> None:
        self._items: dict[str, Takeover] = {}

    def push(self, t: Takeover) -> None:
        self._items[t.instance_id] = t

    def pop(self, instance_id: str) -> None:
        self._items.pop(instance_id, None)

    def expire(self, now: float) -> None:
        for key in [k for k, t in self._items.items() if t.expires_at is not None and t.expires_at <= now]:
            del self._items[key]

    def active(self) -> Takeover | None:
        if not self._items:
            return None
        return max(self._items.values(), key=lambda t: t.priority)

    def __len__(self) -> int:
        return len(self._items)
