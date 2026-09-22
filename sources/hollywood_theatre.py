"""Hollywood Theatre screenings.

The theater's site is WordPress, and every individual screening is a post
in its public REST API (/wp-json/wp/v2/event). The ticketing integration
names each one "<Title> – YYYY-MM-DD H:MMpm", and the slug carries the same
date and time, so the showtime comes from a machine-generated string rather
than prose. Posts are ordered by when they were created, not by showtime, so
paging stops once a whole page is in the past.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import net
from categories import FILM
from models import Event, Window
from text import tidy_title

if TYPE_CHECKING:
    from config import Settings

KEY = "hollywood"
URL = "https://hollywoodtheatre.org/wp-json/wp/v2/event"
VENUE = "Hollywood Theatre"
PER_PAGE = 100
MAX_PAGES = 4

_TITLE = re.compile(
    r"^(?P<name>.+?)\s+[–—-]\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{1,2}:\d{2}\s*[ap]m)\s*$",
    re.IGNORECASE,
)
_SLUG = re.compile(r"-(?P<date>\d{4}-\d{2}-\d{2})-(?P<hour>\d{1,2})(?P<minute>\d{2})(?P<ampm>am|pm)/?$", re.IGNORECASE)

log = logging.getLogger(__name__)


def fetch(settings: Settings, window: Window) -> list[Event]:
    events: list[Event] = []

    for page in range(1, MAX_PAGES + 1):
        params = {"per_page": PER_PAGE, "page": page, "_fields": "id,link,title"}
        try:
            resp = net.get(URL, params=params)
        except Exception as exc:
            if page == 1:
                raise
            log.warning("Hollywood Theatre stopped at page %d: %s", page, exc)
            break

        parsed = [e for item in resp.json() if (e := parse(item, window.tz))]
        events.extend(parsed)

        total_pages = int(resp.headers.get("X-WP-TotalPages", page))
        if page >= total_pages or not any(e.start >= window.start for e in parsed):
            break

    return events


def parse(item: dict, tz) -> Optional[Event]:
    title = html.unescape((item.get("title") or {}).get("rendered", "")).strip()
    link = item.get("link", "")

    name, start = None, None
    match = _TITLE.match(title)
    if match:
        name = match["name"]
        start = _combine(match["date"], match["time"], tz)
    else:
        slug = _SLUG.search(link)
        if slug:
            name = title
            start = _combine(slug["date"], f"{slug['hour']}:{slug['minute']}{slug['ampm']}", tz)

    if not name or not start:
        return None

    return Event(
        name=tidy_title(name),
        start=start,
        venue=VENUE,
        url=link,
        source=KEY,
        category=FILM,
    )


def _combine(day: str, clock: str, tz) -> Optional[datetime]:
    try:
        naive = datetime.strptime(f"{day} {clock.replace(' ', '').lower()}", "%Y-%m-%d %I:%M%p")
    except ValueError:
        return None
    return naive.replace(tzinfo=tz)
