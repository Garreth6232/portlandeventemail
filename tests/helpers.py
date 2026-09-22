from datetime import date, datetime
from pathlib import Path

from config import TIMEZONE
from models import Event, Window

TZ = TIMEZONE
TODAY = date(2026, 9, 22)  # a Tuesday
FIXTURES = Path(__file__).parent / "fixtures"

__all__ = ["TZ", "TODAY", "FIXTURES", "Window", "at", "event"]


def at(month: int, day: int, hour: int = 19, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


def event(name: str = "Show", start: datetime | None = None, venue: str = "Somewhere",
          source: str = "pdxpipeline", **kwargs) -> Event:
    return Event(name=name, start=start or at(9, 22), venue=venue,
                 url="https://example.com", source=source, **kwargs)
