"""Fetch, clean up, and organize one day's digest.

collect() is the only part that touches the network. assemble() is pure,
which is what the tests and the preview script exercise.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from difflib import SequenceMatcher
from itertools import groupby

import requests

import ranking
from config import Preferences, Settings
from models import Event, Window
from sources import registry
from text import normalize

log = logging.getLogger(__name__)

SECTION_TITLES = {"today": "Today", "week": "This Week", "later": "Coming Up"}

# Ticketmaster and SeatGeek list add-ons as if they were events.
_TICKETED_NOISE = re.compile(
    r"\b(parking|suites?|vip package|premium seating|upgrade|season tickets?|gift cards?)\b",
    re.IGNORECASE,
)


@dataclass
class Section:
    key: str
    title: str
    start: date
    end: date
    events: list[Event]  # chosen, best first
    rest: list[Event]    # the ones that didn't make it, by date

    @property
    def overflow(self) -> int:
        return len(self.rest)


@dataclass
class Digest:
    window: Window
    sections: list[Section]
    source_labels: list[str]

    @property
    def total(self) -> int:
        return sum(len(s.events) + s.overflow for s in self.sections)


class NoSourcesAvailable(RuntimeError):
    pass


def build_digest(settings: Settings, today: date) -> Digest:
    window = Window(today, settings.timezone)
    return assemble(collect(settings, window), window, settings.prefs)


def collect(settings: Settings, window: Window) -> list[Event]:
    """Fetch every enabled source in parallel. A source that fails is
    logged and skipped. Raises only if every source failed."""
    sources = registry(settings.prefs)
    enabled = [s for s in sources if s.enabled(settings)]
    for s in sources:
        if s not in enabled:
            log.info("%s: skipped, %s not set", s.label, s.requires.upper())

    events: list[Event] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=len(enabled) or 1) as pool:
        futures = {s: pool.submit(s.fetch, settings, window) for s in enabled}
        for source, future in futures.items():
            try:
                found = future.result()
            except requests.RequestException as exc:
                # The site was down or turned the request away. One line is enough.
                failures += 1
                log.warning("%s: couldn't reach it (%s)", source.label, exc)
                continue
            except Exception:
                # Anything else is probably a bug worth a full traceback.
                failures += 1
                log.exception("%s: fetch failed", source.label)
                continue
            log.info("%s: %d events", source.label, len(found))
            events.extend(found)

    if enabled and failures == len(enabled):
        raise NoSourcesAvailable("Every source failed; not sending an empty digest.")
    return events


def assemble(events: list[Event], window: Window, prefs: Preferences) -> Digest:
    for e in events:
        # Ticketmaster reports UTC. Everything downstream (same-day
        # matching, sections, display) works in Portland time.
        e.start = e.start.astimezone(window.tz)
    events = [e for e in events if window.contains(e.start)]
    events = [e for e in events if not e.ticketed or _keep_ticketed(e, prefs)]

    sources = registry(prefs)
    priority = {s.key: s.priority for s in sources}
    events = group_series(dedupe(events, priority))

    sections = []
    for key, title in SECTION_TITLES.items():
        members = [e for e in events if window.section_for(e.start) == key]
        if not members:
            continue
        chosen, rest = ranking.pick(members, prefs.section_limits[key], prefs)
        start, end = _section_span(key, window)
        sections.append(Section(key, title, start, end, chosen, rest))

    used = {key for s in sections for e in s.events + s.rest for key in e.sources}
    labels = [s.label for s in sources if s.key in used]
    return Digest(window, sections, labels)


def _keep_ticketed(event: Event, prefs: Preferences) -> bool:
    """Ticketed listings survive only at venues named in preferences.toml.
    Big venues are flagged so ranking can cap them."""
    if _TICKETED_NOISE.search(event.name):
        return False
    venue = event.venue.lower()
    if any(v.lower() in venue for v in prefs.big_venues):
        event.big_venue = True
        return True
    return any(v.lower() in venue for v in prefs.small_venues)


def _section_span(key: str, window: Window) -> tuple[date, date]:
    last = (window.end - timedelta(days=1)).date()
    return {
        "today": (window.today, window.today),
        "week": (window.tomorrow.date(), (window.week_end - timedelta(days=1)).date()),
        "later": (window.week_end.date(), last),
    }[key]


# Duplicates -----------------------------------------------------------------

def dedupe(events: list[Event], priority: dict[str, int] | None = None) -> list[Event]:
    """Collapse the same event listed by more than one source.

    Only events on the same day at the same venue are compared. They count
    as the same when the names are close, or when both come from ticketing
    sites and start within half an hour of each other: an arena doesn't run
    two shows at once, even if Ticketmaster calls it "Blazers vs. Lakers"
    and SeatGeek calls it "Los Angeles Lakers at Portland Trail Blazers".
    The copy from the higher-priority source is the one kept.
    """
    if priority is None:
        priority = {s.key: s.priority for s in registry()}

    kept: list[Event] = []
    by_day: dict[date, list[Event]] = {}
    for event in sorted(events, key=lambda e: (-priority.get(e.source, -1), e.start)):
        day = by_day.setdefault(event.start.date(), [])
        match = next((k for k in day if _same_event(k, event)), None)
        if match is None:
            day.append(event)
            kept.append(event)
            continue
        match.sources |= event.sources
        match.price = match.price or event.price
        match.category = match.category or event.category
    return kept


def _same_event(a: Event, b: Event) -> bool:
    if a.source == b.source:
        return a.start == b.start and normalize(a.name) == normalize(b.name)
    if not _same_venue(a.venue, b.venue):
        return False
    gap = abs(a.start - b.start)
    if gap <= timedelta(minutes=90) and _similar(a.name, b.name):
        return True
    return a.ticketed and b.ticketed and gap <= timedelta(minutes=30)


def _same_venue(a: str, b: str) -> bool:
    na, nb = normalize(a), normalize(b)
    return bool(na and nb) and (na in nb or nb in na)


def _similar(a: str, b: str) -> bool:
    na, nb = normalize(a), normalize(b)
    if na == nb or SequenceMatcher(None, na, nb).ratio() >= 0.85:
        return True
    shorter, longer = sorted((set(na.split()), set(nb.split())), key=len)
    return len(shorter) >= 2 and shorter <= longer


# Recurring events ------------------------------------------------------------

def group_series(events: list[Event]) -> list[Event]:
    """Fold repeats (a film's run, weekly trivia, a Saturday market) into
    their first date, with the rest kept in other_dates. Each series then
    appears once, in the section of its next occurrence."""
    def key(e: Event) -> tuple[str, str]:
        return normalize(e.name), normalize(e.venue)

    grouped = []
    for _, group in groupby(sorted(events, key=lambda e: (key(e), e.start)), key=key):
        first, *rest = group
        first.other_dates = [e.start for e in rest]
        for e in rest:
            first.sources |= e.sources
        grouped.append(first)
    return grouped
