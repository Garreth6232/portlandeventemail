"""Settings: secrets and recipients from the environment, everything about
taste from preferences.toml."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from categories import OTHER, canonical
from sources.events_calendar import Calendar

load_dotenv()

PREFERENCES_PATH = Path(__file__).parent / "preferences.toml"
TIMEZONE = ZoneInfo("America/Los_Angeles")
# The scheduled job tries every half hour through the morning and sends from
# the first run that lands in this window. See "Scheduling" in the README.
SEND_FROM = time(7, 45)
SEND_UNTIL = time(12, 0)


@dataclass(frozen=True)
class Preferences:
    latitude: float
    longitude: float
    radius_miles: int
    section_limits: dict[str, int]
    max_per_category: int
    max_big: int
    category_weights: dict[str, float]
    keyword_boosts: dict[str, float]
    favorite_venues: tuple[str, ...]
    venue_boost: float
    big_venues: tuple[str, ...]
    small_venues: tuple[str, ...]
    parks_only: tuple[str, ...]
    calendars: tuple[Calendar, ...] = ()
    subject_lines: tuple[str, ...] = ()
    subject_by_day: dict[str, str] = field(default_factory=dict)
    headers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    movie_theaters: tuple[str, ...] = ()


@dataclass(frozen=True)
class Settings:
    prefs: Preferences
    ticketmaster_api_key: Optional[str]
    seatgeek_client_id: Optional[str]
    smtp_user: Optional[str]      # the Gmail address that sends
    smtp_password: Optional[str]  # its app password
    smtp_host: str
    smtp_port: int
    from_name: str
    recipients: tuple[str, ...]
    timezone: ZoneInfo = TIMEZONE
    send_from: time = SEND_FROM
    send_until: time = SEND_UNTIL


def load_preferences(path: Path = PREFERENCES_PATH) -> Preferences:
    with path.open("rb") as f:
        raw = tomllib.load(f)

    location = raw.get("location", {})
    sections = raw.get("sections", {})
    boosts = raw.get("boosts", {})
    ticketed = raw.get("ticketed", {})

    return Preferences(
        latitude=float(location.get("latitude", 45.5231)),
        longitude=float(location.get("longitude", -122.6680)),
        radius_miles=int(location.get("radius_miles", 15)),
        section_limits={
            "today": int(sections.get("today", 8)),
            "week": int(sections.get("this_week", 12)),
            "later": int(sections.get("coming_up", 12)),
        },
        max_per_category=int(sections.get("max_per_category", 3)),
        max_big=int(sections.get("max_big_venue", 2)),
        category_weights={k.lower(): float(v) for k, v in raw.get("categories", {}).items()},
        keyword_boosts={k.lower(): float(v) for k, v in boosts.get("keywords", {}).items()},
        favorite_venues=tuple(boosts.get("favorite_venues", [])),
        venue_boost=float(boosts.get("venue_boost", 0.0)),
        big_venues=tuple(ticketed.get("big_venues", [])),
        small_venues=tuple(ticketed.get("small_venues", [])),
        parks_only=tuple(p.lower() for p in raw.get("parks", {}).get("only", [])),
        calendars=tuple(_calendar(c) for c in raw.get("calendars", [])),
        subject_lines=tuple(raw.get("subject", {}).get("lines", [])),
        subject_by_day={
            day: line for day, line in raw.get("subject", {}).items()
            if day in _WEEKDAYS and isinstance(line, str)
        },
        headers={
            weather.lower(): tuple([files] if isinstance(files, str) else files)
            for weather, files in raw.get("headers", {}).items()
        },
        movie_theaters=tuple(raw.get("movie_times", {}).get("theaters", [])),
    )


_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday"}


def _calendar(raw: dict) -> Calendar:
    return Calendar(
        name=raw["name"],
        site=raw["site"],
        category=canonical(raw.get("category")) or OTHER,
        include=_lowered(raw.get("include", [])),
        exclude=_lowered(raw.get("exclude", [])),
        cities=_lowered(raw.get("cities", [])),
    )


def _lowered(items: list) -> tuple[str, ...]:
    return tuple(str(i).lower() for i in items)


def load_settings(require_email: bool = True, prefs_path: Path = PREFERENCES_PATH) -> Settings:
    env = os.environ
    recipients = tuple(a.strip() for a in env.get("RECIPIENTS", "").split(",") if a.strip())

    if require_email:
        missing = [
            name
            for name, value in (
                ("GMAIL_ADDRESS", env.get("GMAIL_ADDRESS")),
                ("GMAIL_APP_PASSWORD", env.get("GMAIL_APP_PASSWORD")),
                ("RECIPIENTS", recipients),
            )
            if not value
        ]
        if missing:
            raise SystemExit(
                f"Missing {', '.join(missing)}. Set them in .env locally or as "
                "repository secrets for the scheduled run (see README)."
            )

    return Settings(
        prefs=load_preferences(prefs_path),
        ticketmaster_api_key=env.get("TICKETMASTER_API_KEY") or None,
        seatgeek_client_id=env.get("SEATGEEK_CLIENT_ID") or None,
        smtp_user=(env.get("GMAIL_ADDRESS") or "").strip() or None,
        smtp_password=env.get("GMAIL_APP_PASSWORD") or None,
        smtp_host=env.get("SMTP_HOST") or "smtp.gmail.com",
        smtp_port=int(env.get("SMTP_PORT") or 465),
        from_name=env.get("FROM_NAME") or "Portland Events",
        recipients=recipients,
    )
