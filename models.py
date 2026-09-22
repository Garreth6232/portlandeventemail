"""Data types shared by the sources, the pipeline, and the renderer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

WEEK_DAYS = 7
HORIZON_DAYS = 30


@dataclass
class Event:
    name: str
    start: datetime
    venue: str
    url: str
    source: str
    category: Optional[str] = None
    price: Optional[str] = None
    # Shown instead of the clock time when the start time isn't meaningful,
    # e.g. "All day" for a park event with no set time.
    when: Optional[str] = None
    ticketed: bool = False
    big_venue: bool = False  # arena-scale; capped per section
    sources: set[str] = field(default_factory=set)
    other_dates: list[datetime] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError(f"Event start must be timezone-aware: {self.name!r}")
        self.sources.add(self.source)


@dataclass(frozen=True)
class Window:
    """The span one digest covers: today, the next seven days, and the
    rest of a rolling 30-day horizon.

    A rolling horizon rather than the calendar month, so the third section
    isn't empty for the last week of every month.
    """

    today: date
    tz: ZoneInfo

    @property
    def start(self) -> datetime:
        return datetime.combine(self.today, time(), self.tz)

    @property
    def tomorrow(self) -> datetime:
        return self.start + timedelta(days=1)

    @property
    def week_end(self) -> datetime:
        return self.start + timedelta(days=WEEK_DAYS + 1)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(days=HORIZON_DAYS + 1)

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def section_for(self, moment: datetime) -> Optional[str]:
        if not self.contains(moment):
            return None
        if moment < self.tomorrow:
            return "today"
        if moment < self.week_end:
            return "week"
        return "later"
