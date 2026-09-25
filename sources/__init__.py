"""Every place the digest pulls from.

Fixed sources are listed in SOURCES. Sites running The Events Calendar are
listed in preferences.toml instead, and registry() adds one Source per site.
To add a different kind of source, write a module with a
fetch(settings, window) -> list[Event] function and register it below.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Optional

from models import Event, Window

from . import (
    events_calendar,
    hollywood_theatre,
    pdx_movie_times,
    pdx_pipeline,
    portland_parks,
    seatgeek,
    ticketmaster,
    vine_and_dine,
)

if TYPE_CHECKING:
    from config import Preferences, Settings


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    fetch: Callable[["Settings", Window], list[Event]]
    # When two sources list the same event, the higher-priority copy is kept
    # (it usually has better prices and links).
    priority: int
    ticketed: bool = False
    requires: Optional[str] = None  # Settings attribute that must be set

    def enabled(self, settings: "Settings") -> bool:
        return self.requires is None or bool(getattr(settings, self.requires))


SOURCES: tuple[Source, ...] = (
    Source(ticketmaster.KEY, "Ticketmaster", ticketmaster.fetch, priority=5,
           ticketed=True, requires="ticketmaster_api_key"),
    Source(seatgeek.KEY, "SeatGeek", seatgeek.fetch, priority=4,
           ticketed=True, requires="seatgeek_client_id"),
    Source(hollywood_theatre.KEY, "Hollywood Theatre", hollywood_theatre.fetch, priority=3),
    # Below the theaters' own calendars, above the roundups.
    Source(pdx_movie_times.KEY, "PDX Movie Times", pdx_movie_times.fetch, priority=2),
    Source(portland_parks.KEY, "Portland Parks & Recreation", portland_parks.fetch, priority=2),
    Source(pdx_pipeline.KEY, "PDX Pipeline", pdx_pipeline.fetch, priority=1),
    Source(vine_and_dine.KEY, "PDX Vine and Dine", vine_and_dine.fetch, priority=0),
)

CALENDAR_PRIORITY = 3  # a venue's own calendar beats a roundup that mentions it


def registry(prefs: Optional["Preferences"] = None) -> tuple[Source, ...]:
    calendars = prefs.calendars if prefs else ()
    return SOURCES + tuple(
        Source(c.key, c.name, partial(events_calendar.fetch, c), priority=CALENDAR_PRIORITY)
        for c in calendars
    )
