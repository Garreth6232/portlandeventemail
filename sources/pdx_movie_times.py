"""Showtimes at Portland's independent theaters, from PDX Movie Times.

https://www.pdxmovietimes.com gathers every indie theater's schedule into
one page per day. That covers theaters with no feed of their own
(Laurelhurst, Cinema 21, Academy) and the Hollywood Theatre, whose own
site turns away GitHub's servers. Only the theaters listed under
[movie_times] in preferences.toml are kept, so first-run houses showing
the week's blockbusters stay out.

Each day page is a list of cards, one per film per theater:

    <article class="listing-card">
      <a class="movie-title" href="/movie/batman-1989">Batman</a>
      <div class="meta"><a href="/theater/hollywood-theatre">Hollywood Theatre</a> <span>70mm</span></div>
      <a class="showtime-pill" href="https://tickets...">7:30 PM</a>
    </article>

Their robots.txt allows these pages. tests/fixtures/pdxmovietimes_day.html
is a trimmed version of a real day page (September 2026). If the site
changes its layout, this source goes quiet and the log says it found no
showtimes.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Iterable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import net
from categories import FILM
from models import Event, Window

if TYPE_CHECKING:
    from config import Settings

KEY = "pdxmovietimes"
SITE = "https://www.pdxmovietimes.com"
DAYS = 14  # the site shows two weeks of day pages

_TIME = re.compile(r"(?P<h>\d{1,2}):(?P<m>\d{2})\s*(?P<ampm>[AP]M)", re.IGNORECASE)
_GAUGE = re.compile(r"^\d{2}mm$", re.IGNORECASE)

log = logging.getLogger(__name__)


def fetch(settings: Settings, window: Window) -> list[Event]:
    theaters = settings.prefs.movie_theaters
    events: list[Event] = []
    for offset in range(DAYS):
        day = window.today + timedelta(days=offset)
        try:
            html = net.get(f"{SITE}/day/{day.isoformat()}").text
        except Exception as exc:
            if offset == 0:
                raise
            log.warning("PDX Movie Times stopped at %s: %s", day, exc)
            break
        events.extend(parse_day(html, day, window.tz, theaters))
    if not events:
        log.warning("PDX Movie Times: no showtimes found; has the page layout changed?")
    return events


def parse_day(html: str, day: date, tz, theaters: Iterable[str] = ()) -> list[Event]:
    """Every showtime on one day page, at the theaters wanted. An empty
    `theaters` keeps them all."""
    wanted = tuple(t.lower() for t in theaters)
    events = []
    for card in BeautifulSoup(html, "html.parser").select("article.listing-card"):
        title = card.select_one("a.movie-title")
        theater = card.select_one('a[href^="/theater/"]')
        if title is None or theater is None:
            continue
        venue = theater.get_text(" ", strip=True)
        if wanted and not any(w in venue.lower() for w in wanted):
            continue

        name = _name(title.get_text(" ", strip=True), card)
        page = urljoin(SITE, title.get("href", ""))
        for pill in card.select(".showtime-pill"):
            start = _start(day, pill.get_text(" ", strip=True), tz)
            if start is None:
                continue
            events.append(Event(
                name=name,
                start=start,
                venue=venue,
                url=pill.get("href") or page,
                source=KEY,
                category=FILM,
            ))
    return events


def _name(title: str, card) -> str:
    """The title, plus the print format ("in 70mm") or "double feature"
    when the card says so. Both are keyword boosts in preferences.toml."""
    notes = [s.get_text(" ", strip=True) for s in card.select(".meta span, .tag-blossom")]
    gauge = next((n.lower() for n in notes if _GAUGE.match(n)), None)
    if gauge:
        title = f"{title} in {gauge}"
    if any(n.lower() == "double feature" for n in notes):
        title = f"{title} (double feature)"
    return title


def _start(day: date, text: str, tz) -> Optional[datetime]:
    match = _TIME.search(text)
    if not match:
        return None
    hour, minute = int(match["h"]) % 12, int(match["m"])
    if match["ampm"].upper() == "PM":
        hour += 12
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
