"""Turns a Digest into a subject line, an HTML body, and a plain-text body."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from categories import FILM, OTHER
from mailer.banners import DISPLAY_WIDTH
from models import Event
from pipeline import Digest, Section
from text import normalize

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent.parent / "templates"),
    autoescape=select_autoescape(("html", "j2")),
    trim_blocks=True,
    lstrip_blocks=True,
)

_OVERFLOW = {"today": "today", "week": "this week", "later": "coming up"}
SUBJECT_NAME_LIMIT = 40


# Formatting -----------------------------------------------------------------

def clock(moment: datetime) -> str:
    if (moment.hour, moment.minute) == (12, 0):
        return "noon"
    hour = moment.hour % 12 or 12
    suffix = "am" if moment.hour < 12 else "pm"
    return f"{hour}:{moment.minute:02d} {suffix}" if moment.minute else f"{hour} {suffix}"


def short_day(day: date) -> str:
    return f"{day:%a} {day.month}/{day.day}"


def long_day(day: date) -> str:
    return f"{day:%A}, {day:%B} {day.day}"


def span(section: Section) -> str:
    start, end = section.start, section.end
    if start == end:
        return ""
    if (start.year, start.month) == (end.year, end.month):
        return f"{start:%b} {start.day} to {end.day}"
    return f"{start:%b} {start.day} to {end:%b} {end.day}"


def join(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def more_dates(event: Event) -> str | None:
    dates = event.other_dates
    if not dates:
        return None
    if len(dates) <= 2:
        labels = [clock(d) if d.date() == event.start.date() else short_day(d) for d in dates]
        return "Also " + " and ".join(labels)
    noun = "showings" if event.category == FILM else "dates"
    return f"Runs through {short_day(dates[-1])}, {len(dates) + 1} {noun}"


def _shown_venue(event: Event) -> str | None:
    # "Kenton Farmers Market" at "Kenton Farmers Market" only needs saying once.
    return None if normalize(event.venue) == normalize(event.name) else event.venue


def _shown_category(event: Event) -> str | None:
    return None if event.category == OTHER else event.category


def _row(event: Event, section_key: str) -> dict:
    time_text = event.when or clock(event.start)
    today = section_key == "today"
    return {
        "name": event.name,
        "url": event.url,
        "primary": time_text if today else short_day(event.start),
        "secondary": None if today else time_text,
        "meta": " · ".join(p for p in (_shown_venue(event), _shown_category(event), event.price) if p),
        "more": more_dates(event),
    }


def _context(digest: Digest, from_name: str) -> dict:
    sections = [
        {
            "title": s.title,
            "span": span(s),
            "rows": [_row(e, s.key) for e in sorted(s.events, key=lambda e: e.start)],
            "overflow": f"Plus {s.overflow} more {_OVERFLOW[s.key]}." if s.overflow else None,
        }
        for s in digest.sections
    ]
    counts = [f"{len(s.events) + s.overflow} {_OVERFLOW[s.key]}" for s in digest.sections]
    return {
        "from_name": from_name,
        "date_line": long_day(digest.window.today),
        "preheader": join(counts) if counts else "Nothing new on the calendar.",
        "sections": sections,
        "sources": join(digest.source_labels),
    }


# Output ---------------------------------------------------------------------

def subject(digest: Digest) -> str:
    today = digest.window.today
    prefix = f"{today:%a} {today.month}/{today.day}"
    if not digest.sections:
        return f"{prefix}: nothing new"

    # One name, not two: event titles often contain commas ("Paris, Texas"),
    # which makes a list of them hard to read in a subject line.
    lead = _clip(digest.sections[0].events[0].name)
    rest = digest.total - 1
    return f"{prefix}: {lead} and {rest} more" if rest else f"{prefix}: {lead}"


def html(digest: Digest, from_name: str, banners: dict[str, dict] | None = None) -> str:
    """`banners` maps "header"/"footer" to {"src", "alt"}; see mailer/banners.py."""
    return _env.get_template("digest.html.j2").render(
        **_context(digest, from_name),
        banners=banners or {},
        banner_width=DISPLAY_WIDTH,
    )


def text(digest: Digest, from_name: str) -> str:
    ctx = _context(digest, from_name)
    lines = [ctx["from_name"], ctx["date_line"], ""]

    for section in ctx["sections"]:
        heading = section["title"].upper()
        lines += [f"{heading}  {section['span']}".rstrip(), ""]
        for row in section["rows"]:
            when = row["primary"] if not row["secondary"] else f"{row['primary']}, {row['secondary']}"
            lines += [when, row["name"], row["meta"]]
            if row["more"]:
                lines.append(row["more"])
            lines += [row["url"], ""]
        if section["overflow"]:
            lines += [section["overflow"], ""]

    if ctx["sources"]:
        lines.append(f"Listings from {ctx['sources']}.")
    lines += [
        "Times and prices change, so check the link before you head out.",
        "Reply if you'd like off the list.",
    ]
    return "\n".join(lines).strip() + "\n"


def _clip(name: str) -> str:
    if len(name) <= SUBJECT_NAME_LIMIT:
        return name
    cut = name[:SUBJECT_NAME_LIMIT].rsplit(" ", 1)[0].rstrip(":,-")
    return cut + "…"
