"""Check candidate sources from wherever this runs, and report what each
one offers. Run it from GitHub Actions (the "Probe sources" workflow),
since some sites answer a laptop but turn away GitHub's servers.

    python probe.py

For each site it reports whether robots.txt allows us, whether the pages
load, and what's machine-readable on them: an Events Calendar feed (the
kind sources/events_calendar.py reads), schema.org Event data embedded in
the page, an RSS feed, or an iCalendar link. Nothing here is used by the
digest itself.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

import net
from sources.events_calendar import PATH as EVENTS_CALENDAR_PATH

TIMEOUT = 20
BOT_NAME = "PortlandEventsDigest"


@dataclass(frozen=True)
class Candidate:
    name: str
    site: str
    pages: tuple[str, ...] = ("/",)
    feed: bool = False  # the pages are RSS or Atom feeds


CANDIDATES = (
    # Film
    Candidate("PDX Movie Times", "https://www.pdxmovietimes.com",
              ("/", "/theater/hollywood-theatre", "/theater/laurelhurst-theater", "/theater/cinema-21")),
    Candidate("Hollywood Theatre", "https://hollywoodtheatre.org", ("/", "/wp-json/wp/v2/event?per_page=1")),
    Candidate("Laurelhurst Theater", "https://www.laurelhursttheater.com"),
    Candidate("Cinema 21", "https://www.cinema21.com"),
    Candidate("Academy Theater", "https://www.academytheaterpdx.com"),
    Candidate("Clinton Street Theater", "https://cstpdx.com"),
    Candidate("5th Avenue Cinema", "https://www.5thavenuecinema.org"),
    Candidate("Tomorrow Theater", "https://www.tomorrowtheater.org"),
    # Small music rooms
    Candidate("Mississippi Studios", "https://mississippistudios.com", ("/", "/calendar/")),
    Candidate("Revolution Hall", "https://www.revolutionhall.com", ("/", "/calendar/")),
    Candidate("Polaris Hall", "https://polarishall.com"),
    Candidate("Aladdin Theater", "https://www.aladdin-theater.com"),
    Candidate("Holocene", "https://www.holocene.org"),
    Candidate("Alberta Rose Theatre", "https://www.albertarosetheatre.com"),
    Candidate("Wonder Ballroom", "https://wonderballroom.com"),
    Candidate("Doug Fir Lounge", "https://www.dougfirlounge.com"),
    # Roundups and wine
    Candidate("EverOut Portland", "https://everout.com", ("/portland/events/",)),
    Candidate("Portland Mercury feed", "https://www.portlandmercury.com", ("/feed/",), feed=True),
    Candidate("PDX Vine and Dine feed", "https://pdxvineanddine.substack.com", ("/feed",), feed=True),
    Candidate("Oregon Wine Board", "https://www.oregonwine.org", ("/",)),
)


@dataclass
class Result:
    name: str
    url: str
    status: str
    found: str


def robots_for(site: str) -> robotparser.RobotFileParser | None:
    parser = robotparser.RobotFileParser()
    try:
        resp = net.session().get(urljoin(site, "/robots.txt"), timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code >= 400:
        return None
    parser.parse(resp.text.splitlines())
    return parser


def allowed(robots: robotparser.RobotFileParser | None, url: str) -> bool:
    return robots is None or robots.can_fetch(BOT_NAME, url)


def event_types(html: str) -> list[str]:
    """schema.org Event types in the page's JSON-LD blocks."""
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            kinds = node.get("@type")
            for kind in kinds if isinstance(kinds, list) else [kinds]:
                if isinstance(kind, str) and kind.endswith("Event"):
                    found.append(kind)
            for value in node.values():
                walk(value)

    for script in BeautifulSoup(html, "html.parser").find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(script.string or ""))
        except ValueError:
            continue
    return found


def describe_page(resp: requests.Response, feed: bool) -> str:
    kind = resp.headers.get("Content-Type", "").split(";")[0]
    if "json" in kind:
        try:
            data = resp.json()
        except ValueError:
            return "JSON that doesn't parse"
        return f"JSON, {len(data)} items" if isinstance(data, list) else "JSON"
    if feed or "xml" in kind or "rss" in kind:
        entries = feedparser.parse(resp.content).entries
        return f"feed, {len(entries)} entries: " + "; ".join(e.get("title", "")[:40] for e in entries[:3])

    html = resp.text
    notes = []
    types = event_types(html)
    if types:
        counts = {t: types.count(t) for t in dict.fromkeys(types)}
        notes.append("schema.org " + ", ".join(f"{n} {t}" for t, n in counts.items()))
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("link", type="application/rss+xml"):
        notes.append("RSS link")
    if any(".ics" in a["href"] or "ical" in a["href"].lower() for a in soup.find_all("a", href=True)):
        notes.append("iCal link")
    ticketing = sorted({host for a in soup.find_all("a", href=True)
                        if (host := urlparse(a["href"]).netloc)
                        and any(t in host for t in ("etix", "ticketmaster", "axs", "dice.fm", "eventbrite",
                                                    "tixr", "seetickets", "ticketweb", "showclix", "veezi",
                                                    "fandango", "tixologi"))})
    if ticketing:
        notes.append("tickets via " + ", ".join(ticketing))
    return "; ".join(notes) or f"HTML, {len(html) // 1024}KB, nothing machine-readable found"


def probe(candidate: Candidate) -> list[Result]:
    robots = robots_for(candidate.site)
    urls = [urljoin(candidate.site, p) for p in candidate.pages]
    if not candidate.feed:
        urls.append(urljoin(candidate.site, EVENTS_CALENDAR_PATH))

    results = []
    for url in urls:
        if not allowed(robots, url):
            results.append(Result(candidate.name, url, "robots.txt says no", "skipped"))
            continue
        try:
            resp = net.session().get(url, timeout=TIMEOUT)
        except requests.RequestException as exc:
            results.append(Result(candidate.name, url, "unreachable", type(exc).__name__))
            continue
        found = describe_page(resp, candidate.feed) if resp.ok else ""
        results.append(Result(candidate.name, url, str(resp.status_code), found))
    return results


def main() -> int:
    rows = [r for c in CANDIDATES for r in probe(c)]
    table = ["| Source | URL | Status | What's there |", "| --- | --- | --- | --- |"]
    table += [f"| {r.name} | {r.url} | {r.status} | {r.found.replace('|', '/')} |" for r in rows]
    report = "\n".join(table) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("## Candidate sources, as seen from GitHub\n\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
