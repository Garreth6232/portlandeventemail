"""Decides which listings make each section.

An event's score is its category weight, plus the largest keyword boost it
matches, plus a boost for favorite venues, plus a little for every extra
source that lists it, minus a penalty for long runs (a film playing all
month, weekly trivia). In Today, anything before the evening cutoff (5pm by
default) also loses a little, since the email lands in the morning and
tonight is what's useful. A category label a source made up ("Karaoke",
"Workshop") counts as Other, for its weight and for the per-category cap.
On equal scores, a one-time event beats one that repeats, then the sooner
one wins.

Picking happens in two passes. The first takes the best scorers while
holding each category to max_per_category and each venue to
max_per_venue, so a section shows a spread (a film, a tasting, a show, a
market) instead of eight screenings. The
second fills any seats left over with the best of what's left, so a quiet
week isn't cut short by the variety rule. Big-venue listings are capped in
both passes. The renderer puts the winners back in date order.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from functools import lru_cache
from typing import Collection, Sequence

from categories import LABELS, OTHER
from config import Preferences
from models import Event
from text import normalize

DEFAULT_WEIGHT = 1.0
CONFIRMATION_BONUS = 0.3
MIN_FOR_PICK = 3  # a "top pick" among two listings isn't saying much


@lru_cache(maxsize=256)
def _word(keyword: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])")


def bucket(category: str | None) -> str:
    """The category an event ranks under."""
    return category if category in LABELS else OTHER


def breakdown(event: Event, prefs: Preferences, section: str | None = None) -> dict[str, float]:
    """The parts of an event's score, for explaining a ranking. `section`
    is the section key; Today ranks daytime events lower."""
    text = f"{event.name} {event.venue}".lower()
    matched = [(b, kw) for kw, b in prefs.keyword_boosts.items() if _word(kw).search(text)]
    venue = event.venue.lower()
    return {
        "category": prefs.category_weights.get(bucket(event.category).lower(), DEFAULT_WEIGHT),
        "keyword": max(matched)[0] if matched else 0.0,
        "venue": prefs.venue_boost if any(v.lower() in venue for v in prefs.favorite_venues) else 0.0,
        "sources": CONFIRMATION_BONUS * (len(event.sources) - 1),
        "long run": -prefs.long_run_penalty if _long_run(event, prefs) else 0.0,
        "daytime": -prefs.today_daytime_penalty if _daytime_today(event, prefs, section) else 0.0,
    }


def _daytime_today(event: Event, prefs: Preferences, section: str | None) -> bool:
    """In Today, an event starting before the evening cutoff. The email goes
    out at 8am, when most people are headed to work, so tonight matters
    more than this afternoon. All-day listings count as daytime."""
    return (section == "today" and prefs.today_evening_from is not None
            and (event.when == "All day" or event.start.time() < prefs.today_evening_from))


def _long_run(event: Event, prefs: Preferences) -> bool:
    return prefs.long_run > 0 and len(event.other_dates) + 1 >= prefs.long_run


def score(event: Event, prefs: Preferences, section: str | None = None) -> float:
    return sum(breakdown(event, prefs, section).values())


def _order(prefs: Preferences, section: str | None = None):
    return lambda e: (-score(e, prefs, section), bool(e.other_dates), e.start)


def pick(events: list[Event], limit: int, prefs: Preferences,
         section: str | None = None) -> tuple[list[Event], list[Event]]:
    """Returns (chosen events in score order, the rest in date order)."""
    ranked = sorted(events, key=_order(prefs, section))
    chosen: list[Event] = []
    taken: set[int] = set()
    per_category: Counter[str] = Counter()
    per_venue: Counter[str] = Counter()
    big = 0

    for varied in (True, False):
        for event in ranked:
            if len(chosen) == limit:
                break
            if id(event) in taken:
                continue
            if event.big_venue and big == prefs.max_big:
                continue
            category = bucket(event.category)
            venue = normalize(event.venue)
            if varied and per_category[category] == prefs.max_per_category:
                continue
            if varied and prefs.max_per_venue and per_venue[venue] == prefs.max_per_venue:
                continue
            chosen.append(event)
            taken.add(id(event))
            per_category[category] += 1
            per_venue[venue] += 1
            big += event.big_venue

    chosen.sort(key=_order(prefs, section))
    rest = sorted((e for e in events if id(e) not in taken), key=lambda e: e.start)
    return chosen, rest


def top_pick(chosen: list[Event], day: date, offset: int, rotation: Sequence[str],
             taken: Collection[str] = ()) -> Event | None:
    """The section's top pick, taking turns by category.

    Each day the rotation moves one category along, and each section starts
    `offset` further on, so one email's picks differ and tomorrow's differ
    from today's. The pick is the best listing shown in that category; if
    the section has none, the next category in the rotation is tried.
    Categories in `taken` (earlier sections' picks) are skipped unless
    nothing else fits. `chosen` is best first, as pick() returns it."""
    if len(chosen) < MIN_FOR_PICK:
        return None
    if rotation:
        start = (day.toordinal() + offset) % len(rotation)
        order = rotation[start:] + rotation[:start]
        for category in [c for c in order if c not in taken] + [c for c in order if c in taken]:
            match = next((e for e in chosen if bucket(e.category) == category), None)
            if match:
                return match
    return chosen[0]
