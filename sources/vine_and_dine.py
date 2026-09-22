"""PDX Vine and Dine, a weekly newsletter of Portland wine tastings.

Each post covers the coming weekend. The tastings inside are written as
running prose with no consistent structure, so the post itself becomes one
listing ("the weekend wine roundup") linked to the full write-up, dated to
the Friday of the weekend it covers. Last weekend's post drops off on its
own once that Friday is in the past.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Optional

import feedparser

import net
from categories import FOOD_DRINK
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

KEY = "vineanddine"
FEED_URL = "https://pdxvineanddine.substack.com/feed"
VENUE = "Wine bars and shops around town"
FRIDAY = 4


def fetch(settings: Settings, window: Window) -> list[Event]:
    feed = feedparser.parse(net.get(FEED_URL).content)
    return [e for entry in feed.entries if (e := parse(entry, window.tz))]


def parse(entry, tz) -> Optional[Event]:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not title or not link or not published:
        return None

    friday = weekend_friday(date(*published[:3]))
    return Event(
        name=title,
        start=datetime(friday.year, friday.month, friday.day, 17, tzinfo=tz),
        venue=VENUE,
        url=link,
        source=KEY,
        category=FOOD_DRINK,
        when="All weekend",
    )


def weekend_friday(published: date) -> date:
    """Friday of the weekend a post covers: the coming Friday for a post
    written Monday through Friday, the one just past for Saturday or Sunday."""
    return published - timedelta(days=published.weekday() - FRIDAY)
