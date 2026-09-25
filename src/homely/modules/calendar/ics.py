"""Expand an ICS feed into the concrete events inside a time window (recurrences included)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

import icalendar
import recurring_ical_events


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime  # timezone-aware; midnight local for all-day events
    end: datetime
    all_day: bool
    color: str
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Event:
        return cls(
            title=d["title"],
            start=datetime.fromisoformat(d["start"]),
            end=datetime.fromisoformat(d["end"]),
            all_day=bool(d["all_day"]),
            color=d.get("color", "#4F9DFF"),
            location=d.get("location", ""),
        )


def _as_datetime(value: date | datetime, tz: tzinfo) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
    return datetime.combine(value, time(), tz)


def parse_ics(content: bytes | str, start: datetime, end: datetime, tz: tzinfo, color: str) -> list[Event]:
    """Events overlapping [start, end), in tz, soonest first. Cancelled events are left out."""
    cal = icalendar.Calendar.from_ical(content)
    out: list[Event] = []
    for comp in recurring_ical_events.of(cal).between(start, end):
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        raw_start = comp.get("DTSTART")
        if raw_start is None:
            continue
        s = raw_start.dt
        all_day = not isinstance(s, datetime)
        if comp.get("DTEND") is not None:
            e = comp.get("DTEND").dt
        elif comp.get("DURATION") is not None:
            e = s + comp.get("DURATION").dt
        else:
            e = s + timedelta(days=1) if all_day else s
        begin = _as_datetime(s, tz)
        finish = _as_datetime(e, tz)
        out.append(
            Event(
                title=" ".join(str(comp.get("SUMMARY", "") or "(no title)").split()),
                start=begin,
                end=max(finish, begin),
                all_day=all_day,
                color=color,
                location=" ".join(str(comp.get("LOCATION", "") or "").split()),
            )
        )
    out.sort(key=lambda ev: (ev.start, not ev.all_day, ev.title))
    return out
