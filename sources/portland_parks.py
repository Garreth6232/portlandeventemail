"""Portland Parks & Recreation events, including Summer Free For All (movies
and concerts in the parks), via the Portland Parks Atlas iCalendar feed.

https://parks.portlandciviclab.org/events/calendar.ics
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Iterable, Optional

from icalendar import Calendar

import net
from categories import FESTIVAL, FILM, MARKET, MUSIC, PARKS, VOLUNTEER
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

KEY = "parks"
URL = "https://parks.portlandciviclab.org/events/calendar.ics"
FALLBACK_URL = "https://www.portland.gov/parks/public-events"
ALL_DAY_HOUR = 10  # date-only events sort as mid-morning

# The feed has no categories, so they come from the title. First match
# wins, and film goes first since that's what this source is here for.
_KEYWORDS = (
    (("movie", "film", "cinema", "screening"), FILM),
    (("concert", "music", "band", "orchestra"), MUSIC),
    (("volunteer", "clean-up", "cleanup", "restoration", "weed pull"), VOLUNTEER),
    (("market", "bazaar"), MARKET),
    (("festival", "fair"), FESTIVAL),
)

# City business listed on the parks calendar, not something to go to.
_MEETINGS = re.compile(r"\b(meeting|committee|advisory|hearing|board of)\b", re.IGNORECASE)

log = logging.getLogger(__name__)


def fetch(settings: Settings, window: Window) -> list[Event]:
    content = net.get(URL).content
    return parse_calendar(content, window.tz, settings.prefs.parks_only)


def parse_calendar(content: bytes, tz, only: Iterable[str] = ()) -> list[Event]:
    only = tuple(o.lower() for o in only)
    try:
        calendar = Calendar.from_ical(content)
    except ValueError as exc:
        log.warning("Couldn't parse the Parks calendar: %s", exc)
        return []

    events = []
    for component in calendar.walk("VEVENT"):
        event = _parse(component, tz)
        if event is None:
            continue
        if only and not any(o in f"{event.name} {event.venue}".lower() for o in only):
            continue
        events.append(event)
    return events


def _parse(component, tz) -> Optional[Event]:
    summary = str(component.get("summary") or "").strip()
    dtstart = component.get("dtstart")
    if not summary or dtstart is None or _MEETINGS.search(summary):
        return None

    raw = dtstart.dt
    all_day = not isinstance(raw, datetime)
    if all_day:
        start = datetime(raw.year, raw.month, raw.day, ALL_DAY_HOUR, tzinfo=tz)
    elif raw.tzinfo is None:
        start = raw.replace(tzinfo=tz)
    else:
        start = raw.astimezone(tz)

    haystack = f"{summary} {component.get('description') or ''}".lower()
    category = next((label for words, label in _KEYWORDS if any(w in haystack for w in words)), PARKS)

    return Event(
        name=summary,
        start=start,
        venue=str(component.get("location") or "Portland Parks").strip(),
        url=str(component.get("url") or FALLBACK_URL).strip(),
        source=KEY,
        category=category,
        price="Free",
        when="All day" if all_day else None,
    )
