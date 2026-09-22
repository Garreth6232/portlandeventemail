"""Field names and value shapes in the fixture come from the live feeds of
the Portland Art Museum, Oregon Wine Board, Literary Arts and Portland
Farmers Market, checked September 2026."""
import json
from datetime import datetime

from config import load_preferences
from helpers import FIXTURES, TZ
from sources.events_calendar import Calendar, parse

RAW = {e["id"]: e for e in json.loads((FIXTURES / "events_calendar.json").read_text())["events"]}
ANY = Calendar("Test", "https://example.org")


def test_parses_title_time_venue_and_price():
    e = parse(RAW[1], ANY, TZ)
    assert e.name == "Siren: The Voices of Shelley Beattie w/ Marlee Matlin & Irene Taylor Q&A"
    assert e.start == datetime(2026, 9, 22, 19, tzinfo=TZ)
    assert e.venue == "Portland Art Museum"
    assert e.price == "Free"
    assert e.source == "cal-test"


def test_category_from_site_labels():
    assert parse(RAW[1], ANY, TZ).category == "Film"  # "Screenings & experiences"
    assert parse(RAW[2], ANY, TZ).category == "Food & Drink"  # "Winemaker Dinner"


def test_category_falls_back_to_title_then_site_default():
    talks = Calendar("Literary Arts", "https://literary-arts.org", category="Talks & Readings")
    assert parse(RAW[5], talks, TZ).category == "Talks & Readings"
    wine = Calendar("Wine", "https://x", category="Food & Drink")
    assert parse(RAW[3], wine, TZ).category == "Food & Drink"  # "Winery" in the title


def test_out_of_town_venues_carry_the_city():
    assert parse(RAW[2], ANY, TZ).venue == "The Preserve, McMinnville"


def test_price_ranges_and_cents_are_tidied():
    assert parse(RAW[2], ANY, TZ).price == "$50 to $225"
    assert parse(RAW[4], ANY, TZ).price == "$480"
    assert parse(RAW[6], ANY, TZ).price is None


def test_all_day_events():
    e = parse(RAW[3], ANY, TZ)
    assert e.when == "All day"
    assert e.start.hour == 10


def test_include_exclude_and_city_filters():
    market = Calendar("PFM", "https://x", include=("farmers market",))
    assert parse(RAW[6], market, TZ) is None       # a musician playing the market
    assert parse(RAW[7], market, TZ) is not None   # the market itself

    literary = Calendar("LA", "https://x", exclude=("workshop",))
    assert parse(RAW[4], literary, TZ) is None

    nearby = Calendar("Wine", "https://x", cities=("portland", "mcminnville"))
    assert parse(RAW[2], nearby, TZ) is not None
    assert parse(RAW[3], nearby, TZ) is None        # Salem is too far


def test_missing_venue_uses_the_calendar_name():
    assert parse(RAW[7], Calendar("Portland Farmers Market", "https://x"), TZ).venue == "Portland Farmers Market"


def test_preferences_define_the_calendars():
    names = [c.name for c in load_preferences().calendars]
    assert "Portland Art Museum" in names and "Oregon Wine Board" in names
