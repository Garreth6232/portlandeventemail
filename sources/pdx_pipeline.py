"""PDX Pipeline's weekly roundup: trivia, happy hours, small shows, and the
long tail of bar and neighborhood events nobody sells tickets for.

There's no API. The roundups are items in their RSS feed: "/week/" for
the weekdays and "/weekend/" for Friday through Sunday. By Friday the
weekday one has usually dropped off the feed and only the weekend one is
left. Both are written as day headers followed by list items like:

    <h3>Portland Monday Events, September 21:</h3>
    <li><strong>Comedy:</strong> Marc Price @ Mission Theater | 7PM, ...</li>

Lines that don't fit that shape are skipped. tests/fixtures/pdxpipeline_sample.html
holds a copy of the format; if the test against it fails, they've changed it.
The roundups only cover the current week, so this source never reaches
"Coming Up". Their robots.txt asks for ten seconds between requests.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

import feedparser
from bs4 import BeautifulSoup

import net
from categories import canonical
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

KEY = "pdxpipeline"
FEED_URL = "https://www.pdxpipeline.com/feed/"
WEEK_URL = "https://www.pdxpipeline.com/week/"
ROUNDUP_PATHS = ("/week", "/weekend")
# Other posts can push the roundups off the feed's first page, so look one
# page further back when there's none there.
FEED_PAGES = 2
CRAWL_DELAY = 10  # seconds, from their robots.txt

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_DAY_HEADER = re.compile(r"(?P<month>" + "|".join(_MONTHS) + r")\s+(?P<day>\d{1,2})", re.IGNORECASE)
_LINE = re.compile(
    r"^\**\s*(?P<category>[^:*]{2,30}?)\s*:\**\s*"
    r"(?P<name>.+?)\s*@\s*(?P<venue>.+?)\s*\|\s*"
    r"(?P<time>[^,]{1,20}),?\s*(?P<desc>.*)$"
)
# "4-6PM" starts at 4, so try the range form before the single form.
_TIME_RANGE = re.compile(r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*-\s*\d{1,2}(?::\d{2})?\s*(?P<ampm>am|pm)", re.IGNORECASE)
_TIME = re.compile(r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)", re.IGNORECASE)
_FREE = re.compile(r"\bfree\b", re.IGNORECASE)

log = logging.getLogger(__name__)


def fetch(settings: Settings, window: Window) -> list[Event]:
    for page in range(1, FEED_PAGES + 1):
        if page > 1:
            time.sleep(CRAWL_DELAY)
        params = {"paged": page} if page > 1 else None
        roundups = find_roundups(net.get(FEED_URL, params=params).content)
        if roundups:
            events = []
            for roundup in roundups:
                content = roundup.content[0].value if roundup.get("content") else roundup.get("summary", "")
                events.extend(parse_roundup(content, window.today, window.tz))
            return events

    log.warning("PDX Pipeline: no weekly or weekend roundup in the feed")
    return []


def find_roundups(feed_xml: bytes) -> list:
    """The weekday and weekend roundup entries in one page of the feed."""
    feed = feedparser.parse(feed_xml)
    return [e for e in feed.entries
            if urlparse(e.get("link", "")).path.rstrip("/") in ROUNDUP_PATHS]


def parse_roundup(html: str, today: date, tz) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[Event] = []
    current: Optional[date] = None

    for el in soup.find_all(["h2", "h3", "h4", "li"]):
        if el.name != "li":
            current = _header_date(el.get_text(), today) or current
            continue
        if current is None:
            continue
        event = _parse_line(el, current, tz)
        if event:
            events.append(event)

    return events


def _header_date(text: str, today: date) -> Optional[date]:
    match = _DAY_HEADER.search(text)
    if not match:
        return None
    try:
        candidate = date(today.year, _MONTHS[match["month"].lower()], int(match["day"]))
    except ValueError:
        return None
    if (candidate - today).days < -180:  # a January roundup read in December
        candidate = candidate.replace(year=today.year + 1)
    return candidate


def _parse_line(li, day: date, tz) -> Optional[Event]:
    match = _LINE.match(li.get_text(" ", strip=True))
    if not match:
        return None

    link = li.find("a", href=True)
    time_text = match["time"].strip()
    start, known = _start(day, time_text, tz)

    return Event(
        name=match["name"].strip(),
        start=start,
        venue=match["venue"].strip(),
        url=link["href"] if link else WEEK_URL,
        source=KEY,
        category=canonical(match["category"]),
        price="Free" if _FREE.search(match["desc"]) else None,
        when=None if known else time_text,
    )


def _start(day: date, text: str, tz) -> tuple[datetime, bool]:
    match = _TIME_RANGE.search(text) or _TIME.search(text)
    if not match:
        return datetime(day.year, day.month, day.day, 19, tzinfo=tz), False

    hour, minute = int(match["h"]), int(match["m"] or 0)
    if match["ampm"].lower() == "pm" and hour != 12:
        hour += 12
    elif match["ampm"].lower() == "am" and hour == 12:
        hour = 0
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz), True
