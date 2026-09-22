"""SeatGeek Platform API. Mostly overlaps Ticketmaster; when both list the
same show, the overlap counts as a confirmation in ranking.

https://platform.seatgeek.com/
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import net
from categories import canonical
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

KEY = "seatgeek"
URL = "https://api.seatgeek.com/2/events"
PER_PAGE = 100
MAX_PAGES = 5

log = logging.getLogger(__name__)


def fetch(settings: Settings, window: Window) -> list[Event]:
    prefs = settings.prefs
    tz = window.tz
    events: list[Event] = []

    for page in range(1, MAX_PAGES + 1):
        params = {
            "client_id": settings.seatgeek_client_id,
            "lat": prefs.latitude,
            "lon": prefs.longitude,
            "range": f"{prefs.radius_miles}mi",
            "datetime_local.gte": window.start.strftime("%Y-%m-%dT%H:%M:%S"),
            "datetime_local.lt": window.end.strftime("%Y-%m-%dT%H:%M:%S"),
            "per_page": PER_PAGE,
            "page": page,
            "sort": "datetime_local.asc",
        }
        try:
            data = net.get_json(URL, params=params)
        except Exception as exc:
            if page == 1:
                raise
            log.warning("SeatGeek stopped at page %d: %s", page, exc)
            break

        events.extend(e for raw in data.get("events", []) if (e := parse(raw, tz)))
        if page * PER_PAGE >= (data.get("meta") or {}).get("total", 0):
            break

    return events


def parse(raw: dict, tz) -> Optional[Event]:
    if raw.get("time_tbd") or raw.get("date_tbd"):
        return None

    title = raw.get("title")
    local = raw.get("datetime_local")
    if not title or not local:
        return None

    try:
        # datetime_local is the venue's wall-clock time, with no offset.
        start = datetime.fromisoformat(local).replace(tzinfo=tz)
    except ValueError:
        return None

    taxonomies = raw.get("taxonomies") or [{}]
    stats = raw.get("stats") or {}

    return Event(
        name=title.strip(),
        start=start,
        venue=(raw.get("venue") or {}).get("name") or "Portland",
        url=raw.get("url", ""),
        source=KEY,
        category=canonical(taxonomies[0].get("name")),
        price=_price(stats.get("lowest_price"), stats.get("highest_price")),
        ticketed=True,
    )


def _price(lo, hi) -> Optional[str]:
    if lo is None:
        return None
    if hi is None or round(lo) == round(hi):
        return f"${lo:.0f}"
    return f"${lo:.0f} to ${hi:.0f}"
