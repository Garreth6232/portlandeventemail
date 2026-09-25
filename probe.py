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
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

import net
from sources.events_calendar import PATH as EVENTS_CALENDAR_PATH

TIMEOUT = 15
# A calendar file or subscription link, not just a word containing "ical".
_ICAL = re.compile(r"\.ics\b|[?&]ical=|^webcal:", re.IGNORECASE)
BOT_NAME = "PortlandEventsDigest"
PARALLEL = 8

_local = threading.local()


def session() -> requests.Session:
    """Same headers as the digest's requests, but no retries: a probe
    should report a slow or failing site, not wait it out."""
    if not hasattr(_local, "session"):
        s = requests.Session()
        s.headers.update(net.session().headers)
        _local.session = s
    return _local.session


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
    *(Candidate(f"{name} feed", site, ("/feed/",), feed=True) for name, site in (
        ("Mississippi Studios", "https://mississippistudios.com"),
        ("Revolution Hall", "https://www.revolutionhall.com"),
        ("Aladdin Theater", "https://www.aladdin-theater.com"),
        ("Holocene", "https://www.holocene.org"),
        ("Wonder Ballroom", "https://wonderballroom.com"),
        ("Clinton Street Theater", "https://cstpdx.com"),
    )),
    Candidate("PDX Pipeline feed", "https://www.pdxpipeline.com", ("/feed/", "/feed/?paged=2"), feed=True),
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
        resp = session().get(urljoin(site, "/robots.txt"), timeout=TIMEOUT)
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
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            titles = "; ".join(str(e.get("title", ""))[:40] for e in data["events"][:3])
            return f"Events Calendar JSON, {data.get('total', len(data['events']))} events: {titles}"
        return f"JSON, {len(data)} items" if isinstance(data, list) else "JSON"
    if feed or "xml" in kind or "rss" in kind:
        entries = feedparser.parse(resp.content).entries
        listed = "; ".join(f"{e.get('title', '')[:50]} <{e.get('link', '')}>" for e in entries[:12])
        return f"feed, {len(entries)} entries: {listed}"

    html = resp.text
    notes = []
    types = event_types(html)
    if types:
        counts = {t: types.count(t) for t in dict.fromkeys(types)}
        notes.append("schema.org " + ", ".join(f"{n} {t}" for t, n in counts.items()))
    soup = BeautifulSoup(html, "html.parser")
    base = resp.url
    rss = [urljoin(base, link["href"]) for link in soup.find_all("link", type="application/rss+xml", href=True)]
    if rss:
        notes.append("RSS " + " ".join(rss[:3]))
    ical = list(dict.fromkeys(urljoin(base, a["href"]) for a in soup.find_all("a", href=True)
                              if _ICAL.search(a["href"])))
    if ical:
        notes.append("iCal " + " ".join(ical[:3]))
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
            resp = session().get(url, timeout=TIMEOUT)
        except requests.RequestException as exc:
            results.append(Result(candidate.name, url, "unreachable", type(exc).__name__))
            continue
        found = describe_page(resp, candidate.feed) if resp.ok else ""
        results.append(Result(candidate.name, url, str(resp.status_code), found))
    return results


def sample(url: str, lines: int = 250) -> None:
    """Print what a page holds, to see how a site lays out its listings
    before writing a reader for it: embedded data scripts, then the
    visible text, one element per line. Non-HTML is printed as is."""
    resp = session().get(url, timeout=TIMEOUT)
    print(f"## {url} ({resp.status_code}, {resp.headers.get('Content-Type', '')})")
    if "html" not in resp.headers.get("Content-Type", ""):
        print("\n".join(resp.text.splitlines()[:lines]))
        return
    soup = BeautifulSoup(resp.text, "html.parser")
    for script in soup.find_all("script"):
        body = script.string or ""
        if script.get("src") or len(body) < 200:
            continue
        label = script.get("type") or script.get("id") or "script"
        print(f"[{label}, {len(body)} chars] {body[:300]!r}")
    for tag in soup(["script", "style", "noscript", "svg", "head"]):
        tag.decompose()
    shown = 0
    for el in soup.find_all(True):
        own = "".join(el.find_all(string=True, recursive=False)).strip()
        if not own:
            continue
        classes = ".".join(el.get("class", []))
        href = f" -> {el['href']}" if el.name == "a" and el.get("href") else ""
        print(f"{el.name}{'.' + classes if classes else ''}: {own[:90]}{href[:80]}")
        shown += 1
        if shown >= lines:
            break


def main() -> int:
    if len(sys.argv) > 1:
        for url in sys.argv[1:]:
            sample(url)
        return 0
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        rows = [r for results in pool.map(probe, CANDIDATES) for r in results]
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
