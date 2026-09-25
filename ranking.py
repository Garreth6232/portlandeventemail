"""Decides which listings make each section.

An event's score is its category weight, plus the largest keyword boost it
matches, plus a boost for favorite venues, plus a little for every extra
source that lists it. A category label a source made up ("Karaoke",
"Workshop") counts as Other, for its weight and for the per-category cap.
On equal scores, a one-time event beats one that repeats, then the sooner
one wins.

Picking happens in two passes. The first takes the best scorers while
holding each category to max_per_category, so a section shows a spread
(a film, a tasting, a show, a market) instead of eight screenings. The
second fills any seats left over with the best of what's left, so a quiet
week isn't cut short by the variety rule. Big-venue listings are capped in
both passes. The renderer puts the winners back in date order.
"""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from categories import LABELS, OTHER
from config import Preferences
from models import Event

DEFAULT_WEIGHT = 1.0
CONFIRMATION_BONUS = 0.3


@lru_cache(maxsize=256)
def _word(keyword: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])")


def bucket(category: str | None) -> str:
    """The category an event ranks under."""
    return category if category in LABELS else OTHER


def score(event: Event, prefs: Preferences) -> float:
    weight = prefs.category_weights.get(bucket(event.category).lower(), DEFAULT_WEIGHT)

    text = f"{event.name} {event.venue}".lower()
    boost = max((b for kw, b in prefs.keyword_boosts.items() if _word(kw).search(text)), default=0.0)

    venue = event.venue.lower()
    if any(v.lower() in venue for v in prefs.favorite_venues):
        boost += prefs.venue_boost

    return weight + boost + CONFIRMATION_BONUS * (len(event.sources) - 1)


def _order(prefs: Preferences):
    return lambda e: (-score(e, prefs), bool(e.other_dates), e.start)


def pick(events: list[Event], limit: int, prefs: Preferences) -> tuple[list[Event], list[Event]]:
    """Returns (chosen events in score order, the rest in date order)."""
    ranked = sorted(events, key=_order(prefs))
    chosen: list[Event] = []
    taken: set[int] = set()
    per_category: Counter[str] = Counter()
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
            if varied and per_category[category] == prefs.max_per_category:
                continue
            chosen.append(event)
            taken.add(id(event))
            per_category[category] += 1
            big += event.big_venue

    chosen.sort(key=_order(prefs))
    rest = sorted((e for e in events if id(e) not in taken), key=lambda e: e.start)
    return chosen, rest
