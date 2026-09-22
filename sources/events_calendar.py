"""Any WordPress site running The Events Calendar plugin.

A lot of Portland arts groups use it, and every one of them publishes the
same JSON feed at /wp-json/tribe/events/v1/events. Sites are listed under
[[calendars]] in preferences.toml. To check whether a site qualifies, open
that path on it in a browser: a page of JSON means it works.

https://docs.theeventscalendar.com/reference/rest-api/
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import net
from categories import infer
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

PATH = "/wp-json/tribe/events/v1/events"
PER_PAGE = 50
MAX_PAGES = 6
ALL_DAY_HOUR = 10

_TAGS = re.compile(r"<[^>]+>")
_RANGE_DASH = re.compile(r"\s*[–—]\s*")
_CENTS = re.compile(r"\.00\b")

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Calendar:
    name: str
    site: str
    category: str = "Other"
    include: tuple[str, ...] = ()   # keep only titles containing one of these
    exclude: tuple[str, ...] = ()   # drop titles containing any of these
    cities: tuple[str, ...] = ()    # keep only venues in these cities
    key: str = field(init=False)

    def __post_init__(self) -> None:
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        object.__setattr__(self, "key", f"cal-{slug}")


def fetch(calendar: Calendar, settings: Settings, window: Window) -> list[Event]:
    url: Optional[str] = calendar.site.rstrip("/") + PATH
    params: Optional[dict] = {
        "start_date": window.start.strftime("%Y-%m-%d"),
        "end_date": window.end.strftime("%Y-%m-%d"),
        "per_page": PER_PAGE,
    }
    events: list[Event] = []

    for page in range(MAX_PAGES):
        try:
            data = net.get_json(url, params=params)
        except Exception as exc:
            if page == 0:
                raise
            log.warning("%s stopped at page %d: %s", calendar.name, page + 1, exc)
            break

        events.extend(e for raw in data.get("events", []) if (e := parse(raw, calendar, window.tz)))
        url, params = data.get("next_rest_url"), None  # next_rest_url carries its own query
        if not url:
            break

    return events


def parse(raw: dict, calendar: Calendar, tz: ZoneInfo) -> Optional[Event]:
    title = html.unescape(_TAGS.sub("", raw.get("title") or "")).strip()
    link = raw.get("url")
    start_raw = raw.get("start_date")
    if not title or not link or not start_raw:
        return None

    lowered = title.lower()
    if calendar.include and not any(w in lowered for w in calendar.include):
        return None
    if any(w in lowered for w in calendar.exclude):
        return None

    venue = raw.get("venue") if isinstance(raw.get("venue"), dict) else {}
    city = (venue.get("city") or "").strip()
    if calendar.cities and city.lower() not in calendar.cities:
        return None

    try:
        start = datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    all_day = bool(raw.get("all_day"))
    if all_day:
        start = start.replace(hour=ALL_DAY_HOUR, minute=0)

    return Event(
        name=title,
        start=start.replace(tzinfo=_zone(raw.get("timezone"), tz)),
        venue=_venue_label(venue, calendar.name, city),
        url=link,
        source=calendar.key,
        category=infer(title, [html.unescape(c.get("name", "")) for c in raw.get("categories") or []],
                       calendar.category),
        price=_price(raw.get("cost")),
        when="All day" if all_day else None,
    )


def _zone(name: Optional[str], fallback: ZoneInfo) -> ZoneInfo:
    if not name:
        return fallback
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return fallback


def _venue_label(venue: dict, fallback: str, city: str) -> str:
    name = html.unescape(venue.get("venue") or "").strip() or fallback
    if city and city.lower() != "portland" and city.lower() not in name.lower():
        return f"{name}, {city}"
    return name


def _price(cost: Optional[str]) -> Optional[str]:
    cost = html.unescape(cost or "").strip()
    if not cost:
        return None
    return _CENTS.sub("", _RANGE_DASH.sub(" to ", cost))
