import json
import time
from datetime import date, datetime, timezone

from helpers import FIXTURES, TODAY, TZ, Window
from sources import (hollywood_theatre, pdx_movie_times, pdx_pipeline, portland_parks, seatgeek,
                     ticketmaster, vine_and_dine)


# Ticketmaster ----------------------------------------------------------------

TM_EVENT = {
    "name": "Hozier",
    "url": "https://www.ticketmaster.com/event/1",
    "dates": {"start": {"dateTime": "2026-10-04T03:00:00Z"}, "status": {"code": "onsale"}},
    "_embedded": {"venues": [{"name": "Moda Center"}]},
    "classifications": [{"segment": {"name": "Music"}}],
    "priceRanges": [{"min": 65.0, "max": 150.0}],
}


def test_ticketmaster_parse():
    e = ticketmaster.parse(TM_EVENT)
    assert e.name == "Hozier"
    assert e.start == datetime(2026, 10, 4, 3, tzinfo=timezone.utc)
    assert e.venue == "Moda Center"
    assert e.category == "Music"
    assert e.price == "$65 to $150"
    assert e.ticketed


def test_ticketmaster_skips_cancelled_and_tba():
    cancelled = {**TM_EVENT, "dates": {**TM_EVENT["dates"], "status": {"code": "cancelled"}}}
    tba = {**TM_EVENT, "dates": {"start": {"localDate": "2026-10-04"}}}
    assert ticketmaster.parse(cancelled) is None
    assert ticketmaster.parse(tba) is None


def test_ticketmaster_window_is_sent_in_utc():
    start = Window(TODAY, TZ).start  # midnight Pacific
    assert ticketmaster._api_time(start) == "2026-09-22T07:00:00Z"


# SeatGeek ----------------------------------------------------------------------

SG_EVENT = {
    "title": "Utah Jazz at Portland Trail Blazers",
    "url": "https://seatgeek.com/e/1",
    "datetime_local": "2026-10-08T19:00:00",
    "venue": {"name": "Moda Center"},
    "taxonomies": [{"name": "nba"}],
    "stats": {"lowest_price": 41, "highest_price": 395},
}


def test_seatgeek_parse():
    e = seatgeek.parse(SG_EVENT, TZ)
    assert e.start == datetime(2026, 10, 8, 19, tzinfo=TZ)
    assert e.category == "Sports"
    assert e.price == "$41 to $395"


def test_seatgeek_skips_time_tbd():
    assert seatgeek.parse({**SG_EVENT, "time_tbd": True}, TZ) is None


# Hollywood Theatre -----------------------------------------------------------

def hollywood_events():
    items = json.loads((FIXTURES / "hollywood_events.json").read_text())
    return [hollywood_theatre.parse(item, TZ) for item in items]


def test_hollywood_reads_showtime_from_title():
    dance, combat, misty, *_ = hollywood_events()
    assert dance.name == "Hellavision Television – DANCE EVERYWHERE"
    assert dance.start == datetime(2026, 10, 24, 19, tzinfo=TZ)
    assert combat.start == datetime(2026, 10, 6, 19, 30, tzinfo=TZ)
    assert misty.start == datetime(2026, 10, 19, 19, tzinfo=TZ)


def test_hollywood_tidies_all_caps_titles():
    _, combat, misty, jack, _ = hollywood_events()
    assert combat.name == "Immortal Combat"
    assert misty.name == "Misty Green"
    assert jack.name == "Violence Jack: OVA Collection"


def test_hollywood_falls_back_to_slug_and_skips_undated_posts():
    *_, jack, membership = hollywood_events()
    assert jack.start == datetime(2026, 9, 27, 21, 30, tzinfo=TZ)
    assert membership is None


# Portland Parks ----------------------------------------------------------------

def parks(only=()):
    return portland_parks.parse_calendar((FIXTURES / "parks_atlas_sample.ics").read_bytes(), TZ, only)


def test_parks_parses_feed():
    names = {e.name for e in parks()}
    assert "Movies in the Park: Laurelhurst Park" in names
    assert len(names) == 4


def test_parks_categories_from_titles():
    by_name = {e.name: e for e in parks()}
    assert by_name["Movies in the Park: Laurelhurst Park"].category == "Film"
    assert by_name["Summer Concert Series: Mt. Tabor Park"].category == "Music"
    assert by_name["Pittock Garden Tuesday Volunteer Day"].category == "Volunteer"
    assert by_name["Fall Leaf Peeping Walk: Laurelhurst Park"].category == "Parks"


def test_parks_all_day_events():
    walk = next(e for e in parks() if "Leaf Peeping" in e.name)
    assert walk.start.date() == date(2026, 9, 30)
    assert walk.when == "All day"


def test_parks_filter():
    kept = parks(["laurelhurst"])
    assert len(kept) == 2
    assert all("laurelhurst" in f"{e.name} {e.venue}".lower() for e in kept)


# PDX Pipeline ------------------------------------------------------------------

def test_pdx_pipeline_parses_roundup():
    html = (FIXTURES / "pdxpipeline_sample.html").read_text()
    events = pdx_pipeline.parse_roundup(html, date(2026, 9, 20), TZ)
    by_name = {e.name: e for e in events}

    assert len(events) == 4
    assert by_name["Marc Price"].venue == "Mission Theater"
    assert by_name["Marc Price"].start == datetime(2026, 9, 21, 19, tzinfo=TZ)
    assert by_name["Taco Tuesday Extended"].start.hour == 16  # "4-6PM" starts at 4
    assert by_name["Taco Tuesday Extended"].category == "Happy Hour"
    assert by_name["Indie Night"].url == "https://www.pdxpipeline.com/some-indie-show"


def test_pdx_pipeline_keeps_unparseable_time_text():
    html = "<h3>Tuesday, September 22:</h3><ul><li><strong>Music:</strong> Band @ Bar | Doors at dusk, fun.</li></ul>"
    (e,) = pdx_pipeline.parse_roundup(html, TODAY, TZ)
    assert e.when == "Doors at dusk"


def test_pdx_pipeline_ignores_lines_before_a_date():
    html = "<ul><li><strong>Music:</strong> Band @ Bar | 8PM, no date.</li></ul>"
    assert pdx_pipeline.parse_roundup(html, TODAY, TZ) == []


# PDX Vine and Dine -------------------------------------------------------------

def test_vine_and_dine_weekend_dating():
    assert vine_and_dine.weekend_friday(date(2026, 9, 22)) == date(2026, 9, 25)  # Tue
    assert vine_and_dine.weekend_friday(date(2026, 9, 25)) == date(2026, 9, 25)  # Fri
    assert vine_and_dine.weekend_friday(date(2026, 9, 27)) == date(2026, 9, 25)  # Sun


def test_vine_and_dine_parse():
    entry = {
        "title": "This Weekend in Wine",
        "link": "https://pdxvineanddine.substack.com/p/x",
        "published_parsed": time.strptime("2026-09-24", "%Y-%m-%d"),
    }
    e = vine_and_dine.parse(entry, TZ)
    assert e.start == datetime(2026, 9, 25, 17, tzinfo=TZ)
    assert e.category == "Food & Drink"
    assert e.when == "All weekend"


def test_vine_and_dine_skips_incomplete_entries():
    assert vine_and_dine.parse({"title": "No link"}, TZ) is None


def _feed(*links):
    items = "".join(
        f"<item><title>t</title><link>{link}</link><description><![CDATA[x]]></description></item>"
        for link in links
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'.encode()


def _serve_feed(monkeypatch, pages, fail=()):
    """Stand in for the feed: pages maps a page number (None for the first)
    to feed XML. Returns the pages asked for and the sleeps taken."""
    import requests
    asked, slept = [], []

    class Resp:
        def __init__(self, content):
            self.content = content

    def fake_get(url, params=None):
        page = (params or {}).get("paged")
        asked.append(page)
        if page in fail:
            raise requests.ConnectionError("gone")
        return Resp(pages[page])

    monkeypatch.setattr(pdx_pipeline.net, "get", fake_get)
    monkeypatch.setattr(pdx_pipeline.time, "sleep", slept.append)
    monkeypatch.setattr(pdx_pipeline, "parse_roundup", lambda html, today, tz, url: [url])
    return asked, slept


def test_pdx_pipeline_looks_on_the_second_feed_page(monkeypatch):
    asked, slept = _serve_feed(monkeypatch, {
        None: _feed("https://www.pdxpipeline.com/2026/09/25/a-post/"),
        2: _feed("https://www.pdxpipeline.com/week/", "https://www.pdxpipeline.com/older/"),
    })
    assert pdx_pipeline.fetch(None, Window(TODAY, TZ)) == ["https://www.pdxpipeline.com/week/"]
    assert asked == [None, 2]
    assert slept == [pdx_pipeline.CRAWL_DELAY]  # their robots.txt asks for it


def test_pdx_pipeline_finds_the_weekday_roundup_on_page_two_when_the_weekend_one_is_up(monkeypatch):
    # A Thursday: the new weekend post is on top, the weekday one has slid back.
    asked, _ = _serve_feed(monkeypatch, {
        None: _feed("https://www.pdxpipeline.com/weekend/"),
        2: _feed("https://www.pdxpipeline.com/week/"),
    })
    got = pdx_pipeline.fetch(None, Window(TODAY, TZ))
    assert sorted(got) == ["https://www.pdxpipeline.com/week/", "https://www.pdxpipeline.com/weekend/"]
    assert asked == [None, 2]


def test_pdx_pipeline_stops_once_both_roundups_are_found(monkeypatch):
    asked, slept = _serve_feed(monkeypatch, {
        None: _feed("https://www.pdxpipeline.com/weekend/", "https://www.pdxpipeline.com/week/"),
    })
    assert len(pdx_pipeline.fetch(None, Window(TODAY, TZ))) == 2
    assert asked == [None] and slept == []


def test_pdx_pipeline_keeps_page_one_when_page_two_fails(monkeypatch):
    _serve_feed(monkeypatch, {None: _feed("https://www.pdxpipeline.com/weekend/")}, fail={2})
    assert pdx_pipeline.fetch(None, Window(TODAY, TZ)) == ["https://www.pdxpipeline.com/weekend/"]


def test_pdx_pipeline_lines_without_a_link_point_at_their_roundup():
    html = "<h3>Portland Friday Events, September 25:</h3><ul><li><strong>Music:</strong> Show @ Bar | 8PM</li></ul>"
    (e,) = pdx_pipeline.parse_roundup(html, date(2026, 9, 25), TZ, "https://www.pdxpipeline.com/weekend/")
    assert e.url == "https://www.pdxpipeline.com/weekend/"


def test_pdx_pipeline_reads_the_weekend_roundup_too():
    feed = _feed("https://www.pdxpipeline.com/weekend/",
                 "https://www.pdxpipeline.com/portland-in-the-news-september-24-2026/",
                 "https://www.pdxpipeline.com/week/",
                 "https://www.pdxpipeline.com/weekend-brunch-guide-2026/")
    links = [e.link for e in pdx_pipeline.find_roundups(feed)]
    assert links == ["https://www.pdxpipeline.com/weekend/", "https://www.pdxpipeline.com/week/"]


def _movie_day(theaters=()):
    html = (FIXTURES / "pdxmovietimes_day.html").read_text()
    return pdx_movie_times.parse_day(html, date(2026, 9, 26), TZ, theaters)


def test_pdx_movie_times_reads_every_showtime():
    events = _movie_day()
    assert len(events) == 8
    coyote = [e for e in events if e.name == "Coyote vs. Acme"]
    assert [e.start.strftime("%H:%M") for e in coyote] == ["12:45", "16:00", "18:45"]
    assert all(e.venue == "Laurelhurst Theater" and e.category == "Film" for e in coyote)
    assert coyote[0].url.endswith("rtsPerformanceID=045773000021")


def test_pdx_movie_times_keeps_only_listed_theaters():
    events = _movie_day(["Hollywood Theatre", "laurelhurst"])
    assert {e.venue for e in events} == {"Hollywood Theatre", "Laurelhurst Theater"}


def test_pdx_movie_times_notes_format_and_double_features():
    names = {e.name for e in _movie_day()}
    assert "Batman in 70mm" in names
    assert "Obsession (double feature)" in names


def test_pdx_movie_times_static_showtime_links_to_the_film_page():
    (obsession,) = [e for e in _movie_day() if e.name.startswith("Obsession")]
    assert obsession.start.hour == 21
    assert obsession.url == "https://www.pdxmovietimes.com/movie/obsession"


def test_pdx_movie_times_morning_and_noon_times():
    starts = {e.name: e.start for e in _movie_day()}
    assert starts["Avengers: Endgame"].strftime("%H:%M") == "09:45"
    coyote = min(e.start for e in _movie_day() if e.name == "Coyote vs. Acme")
    assert coyote.strftime("%H:%M") == "12:45"


def test_pdx_movie_times_fetches_each_day_and_stops_on_a_later_failure(monkeypatch, prefs):
    import requests
    from dataclasses import replace
    html = (FIXTURES / "pdxmovietimes_day.html").read_text()
    asked = []

    class Resp:
        text = html

    def fake_get(url, **kwargs):
        asked.append(url)
        if len(asked) == 3:
            raise requests.ConnectionError("gone")
        return Resp()

    laurelhurst_only = replace(prefs, movie_theaters=("Laurelhurst",))

    class Settings:
        prefs = laurelhurst_only

    monkeypatch.setattr(pdx_movie_times.net, "get", fake_get)
    events = pdx_movie_times.fetch(Settings, Window(TODAY, TZ))
    assert asked[:2] == ["https://www.pdxmovietimes.com/day/2026-09-22",
                         "https://www.pdxmovietimes.com/day/2026-09-23"]
    assert len(asked) == 3 and len(events) == 6  # three Laurelhurst showtimes a day, two days


def test_pdx_movie_times_showtimes_fold_into_one_listing(window, prefs):
    from pipeline import assemble
    html = (FIXTURES / "pdxmovietimes_day.html").read_text()
    events = [e for day in (date(2026, 9, 22), date(2026, 9, 23))
              for e in pdx_movie_times.parse_day(html, day, TZ, ["Laurelhurst"])]
    digest = assemble(events, window, prefs)
    (coyote,) = [e for s in digest.sections for e in s.events + s.rest]
    assert len(coyote.other_dates) == 5
