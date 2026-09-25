"""Turns a Digest into a subject line, an HTML body, and a plain-text body."""
from __future__ import annotations

from datetime import date, datetime
from itertools import groupby
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, FileSystemLoader, select_autoescape

import categories as cat
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
_MORE_TITLES = {"today": "Also today", "week": "Also this week", "later": "Also coming up"}

# Gmail hides everything past about 102KB of HTML behind "View entire
# message". The full list at the bottom shrinks until the email fits.
HTML_BUDGET = 95_000
PREVIEW_NAME_LIMIT = 40
MIN_FOR_PICK = 3  # a "top pick" among two listings isn't saying much

# Subject lines rotate by date, so a re-run on the same day gets the same one.
# Override or add to these under [subject] in preferences.toml.
DEFAULT_SUBJECTS = (
    "Good morning, Portland! {date}",
    "Rise and shine, Portland: {date}",
    "Morning! Here's Portland for {weekday}",
    "What's on in Portland, {date}",
    "Hello, Portland! Your {weekday} lineup",
    "Portland, {weekday} edition",
    "Coffee's on. Here's Portland for {date}",
)
DEFAULT_DAY_SUBJECTS = {
    "monday": "New week, Portland! {date}",
    "friday": "Happy Friday, Portland! Here's the weekend",
}

# Category labels are colored so a glance down the list shows the mix.
# All of these clear WCAG AA contrast on white.
CATEGORY_COLORS = {
    cat.FILM: "#b0283c",
    cat.FOOD_DRINK: "#7a2553",
    cat.MUSIC: "#1c6a86",
    cat.COMEDY: "#a24b00",
    cat.ARTS: "#6a4595",
    cat.TALKS: "#4f6420",
    cat.SPORTS: "#1d4a86",
    cat.PARKS: "#23733a",
    cat.MARKET: "#80620a",
    cat.FESTIVAL: "#b3185a",
    cat.FAMILY: "#00766b",
    cat.TRIVIA: "#6b4a3a",
    cat.HAPPY_HOUR: "#98470f",
    cat.VOLUNTEER: "#4d5f69",
}
DEFAULT_COLOR = "#5f5f5f"


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
    noun = "showings" if event.category == cat.FILM else "dates"
    return f"Runs through {short_day(dates[-1])}, {len(dates) + 1} {noun}"


def is_free(price: str | None) -> bool:
    return bool(price) and price.lower().startswith("free")


def _shown_venue(event: Event) -> str | None:
    # "Kenton Farmers Market" at "Kenton Farmers Market" only needs saying once.
    return None if normalize(event.venue) == normalize(event.name) else event.venue


def _label(event: Event) -> str | None:
    return None if event.category in (None, cat.OTHER) else event.category


def _row(event: Event, section_key: str, pick: bool) -> dict:
    time_text = event.when or clock(event.start)
    today = section_key == "today"
    return {
        "name": event.name,
        "url": event.url,
        "primary": time_text if today else short_day(event.start),
        "secondary": None if today else time_text,
        "label": _label(event),
        "color": CATEGORY_COLORS.get(event.category, DEFAULT_COLOR),
        "pick": pick,
        "venue": _shown_venue(event),
        "price": event.price,
        "free": is_free(event.price),
        "more": more_dates(event),
    }


def _line(event: Event) -> dict:
    """One compact line in the full list at the bottom."""
    return {
        "when": event.when or clock(event.start),
        "name": event.name,
        "url": event.url,
        "venue": _shown_venue(event),
    }


def _by_day(events: list[Event], section_key: str) -> list[dict]:
    """The full list's lines grouped under day headings. Today's need none."""
    if section_key == "today":
        return [{"day": None, "lines": [_line(e) for e in events]}]
    return [
        {"day": short_day(day), "lines": [_line(e) for e in group]}
        for day, group in groupby(events, key=lambda e: e.start.date())
    ]


def _section(s: Section, more_limit: int | None = None) -> dict:
    """`more_limit` caps how many of the rest get a line at the bottom;
    None means all of them."""
    # s.events arrive best-first; the first one is the section's top pick.
    top = s.events[0] if len(s.events) >= MIN_FOR_PICK else None
    listed = s.rest if more_limit is None else s.rest[:more_limit]
    return {
        "key": s.key,
        "title": s.title,
        "span": span(s),
        "rows": [_row(e, s.key, e is top) for e in sorted(s.events, key=lambda e: e.start)],
        "overflow": _overflow_line(s, len(listed)),
        "more_title": _MORE_TITLES[s.key],
        "more": _by_day(listed, s.key) if listed else [],
        "unlisted": s.overflow - len(listed),
    }


def _overflow_line(s: Section, listed: int) -> str | None:
    if not s.overflow:
        return None
    where = _OVERFLOW[s.key]
    if not listed:
        return f"Plus {s.overflow} more {where}."
    return f"Plus {s.overflow} more {where}, listed at the bottom."


def _preheader(digest: Digest) -> str:
    """The grey line inbox apps show after the subject."""
    if not digest.sections:
        return "Nothing new on the calendar."
    first = digest.sections[0]
    names = [_clip(e.name) for e in first.events[:2]]
    rest = digest.total - len(names)
    lead = f"{first.title}: {' and '.join(names)}"
    return f"{lead}, plus {rest} more" if rest else lead


def _limits(digest: Digest, total: int | None) -> list[int | None]:
    """Split `total` lines at the bottom across sections in order, so the
    nearest dates keep theirs and Coming Up is trimmed first."""
    if total is None:
        return [None] * len(digest.sections)
    limits = []
    for s in digest.sections:
        take = min(total, s.overflow)
        limits.append(take)
        total -= take
    return limits


def _context(digest: Digest, from_name: str, weather_line: str | None = None,
             more_total: int | None = None) -> dict:
    counts = [f"{len(s.events) + s.overflow} {_OVERFLOW[s.key]}" for s in digest.sections]
    sections = [_section(s, limit) for s, limit in zip(digest.sections, _limits(digest, more_total))]
    return {
        "from_name": from_name,
        "date_line": long_day(digest.window.today),
        "weather": weather_line,
        "summary": join(counts),
        "preheader": _preheader(digest),
        "sections": sections,
        "has_more": any(sec["more"] for sec in sections),
        "sources": join(digest.source_labels),
    }


# Output ---------------------------------------------------------------------

def subject(digest: Digest, lines: Sequence[str] = DEFAULT_SUBJECTS,
            by_day: dict[str, str] | None = None) -> str:
    today = digest.window.today
    by_day = DEFAULT_DAY_SUBJECTS if by_day is None else by_day
    template = by_day.get(f"{today:%A}".lower()) or lines[today.toordinal() % len(lines)]
    return template.format(date=f"{today:%A}, {today:%b} {today.day}", weekday=f"{today:%A}")


def html(digest: Digest, from_name: str, banners: dict[str, dict] | None = None,
         weather_line: str | None = None) -> str:
    """`banners` maps "header"/"footer" to {"src", "alt"}; see mailer/banners.py.

    Everything that didn't make a section is listed compactly at the
    bottom. On a very full day that list is cut short, from the far end,
    to keep the email under Gmail's clipping size."""
    template = _env.get_template("digest.html.j2")

    def render_with(more_total: int | None) -> str:
        return template.render(
            **_context(digest, from_name, weather_line, more_total),
            banners=banners or {},
            width=DISPLAY_WIDTH,
        )

    out = render_with(None)
    total = sum(s.overflow for s in digest.sections)
    while len(out.encode()) > HTML_BUDGET and total > 0:
        total = max(0, total - 10)
        out = render_with(total)
    return out


def text(digest: Digest, from_name: str, weather_line: str | None = None) -> str:
    ctx = _context(digest, from_name, weather_line)
    lines = [ctx["from_name"], ctx["date_line"]]
    if ctx["weather"]:
        lines.append(ctx["weather"])
    lines.append("")

    for section in ctx["sections"]:
        lines += [f"{section['title'].upper()}  {section['span']}".rstrip(), ""]
        for row in section["rows"]:
            when = row["primary"] if not row["secondary"] else f"{row['primary']}, {row['secondary']}"
            label = " · ".join(p for p in (row["label"], "Top pick" if row["pick"] else None) if p)
            meta = " · ".join(p for p in (row["venue"], row["price"]) if p)
            lines += [f"{when}  {label}".rstrip(), row["name"]]
            if meta:
                lines.append(meta)
            if row["more"]:
                lines.append(row["more"])
            lines += [row["url"], ""]
        if section["overflow"]:
            lines += [section["overflow"], ""]

    for section in ctx["sections"]:
        if not section["more"]:
            continue
        lines += [section["more_title"].upper(), ""]
        for day in section["more"]:
            if day["day"]:
                lines.append(day["day"])
            for line in day["lines"]:
                venue = f" · {line['venue']}" if line["venue"] else ""
                lines += [f"  {line['when']}  {line['name']}{venue}", f"  {line['url']}"]
            lines.append("")
        if section["unlisted"]:
            lines += [f"And {section['unlisted']} more.", ""]

    if ctx["sources"]:
        lines.append(f"Listings from {ctx['sources']}.")
    lines += [
        "Times and prices change, so check the link before you head out.",
        "Reply if you'd like off the list.",
    ]
    return "\n".join(lines).strip() + "\n"


def _clip(name: str) -> str:
    if len(name) <= PREVIEW_NAME_LIMIT:
        return name
    cut = name[:PREVIEW_NAME_LIMIT].rsplit(" ", 1)[0].rstrip(":,-")
    return cut + "…"
