"""Ticketmaster Discovery API. Only big-venue events survive the pipeline;
see [ticketed] in preferences.toml.

https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import net
from categories import canonical
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

KEY = "ticketmaster"
URL = "https://app.ticketmaster.com/discovery/v2/events.json"
PAGE_SIZE = 200
MAX_PAGES = 5  # the API refuses to page past 1,000 results anyway
SKIP_STATUSES = {"cancelled", "postponed"}

log = logging.getLogger(__name__)


def fetch(settings: Settings, window: Window) -> list[Event]:
    prefs = settings.prefs
    events: list[Event] = []

    for page in range(MAX_PAGES):
        params = {
            "apikey": settings.ticketmaster_api_key,
            "latlong": f"{prefs.latitude},{prefs.longitude}",
            "radius": prefs.radius_miles,
            "unit": "miles",
            "startDateTime": _api_time(window.start),
            "endDateTime": _api_time(window.end),
            "size": PAGE_SIZE,
            "page": page,
            "sort": "date,asc",
        }
        try:
            data = net.get_json(URL, params=params)
        except Exception as exc:
            if page == 0:
                raise
            log.warning("Ticketmaster stopped at page %d: %s", page, exc)
            break

        events.extend(e for raw in data.get("_embedded", {}).get("events", []) if (e := parse(raw)))
        if page + 1 >= data.get("page", {}).get("totalPages", 0):
            break

    return events


def _api_time(moment: datetime) -> str:
    # The API wants UTC with a literal Z. Formatting a Pacific time with a
    # "Z" suffix would shift the whole window by 7 or 8 hours.
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(raw: dict) -> Optional[Event]:
    dates = raw.get("dates") or {}
    if (dates.get("status") or {}).get("code") in SKIP_STATUSES:
        return None

    start_raw = (dates.get("start") or {}).get("dateTime")
    name = raw.get("name")
    if not start_raw or not name:
        return None  # "time TBA" listings would land in the wrong section

    try:
        start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
    except ValueError:
        return None

    venues = (raw.get("_embedded") or {}).get("venues") or [{}]
    classification = (raw.get("classifications") or [{}])[0]
    segment = (classification.get("segment") or {}).get("name")
    genre = (classification.get("genre") or {}).get("name")

    return Event(
        name=name.strip(),
        start=start,
        venue=venues[0].get("name") or "Portland",
        url=raw.get("url", ""),
        source=KEY,
        category=canonical(segment if segment and segment != "Undefined" else genre),
        price=_price(raw.get("priceRanges")),
        ticketed=True,
    )


def _price(ranges: Optional[list]) -> Optional[str]:
    if not ranges:
        return None
    lo, hi = ranges[0].get("min"), ranges[0].get("max")
    if lo is None:
        return None
    if hi is None or round(lo) == round(hi):
        return f"${lo:.0f}"
    return f"${lo:.0f} to ${hi:.0f}"
