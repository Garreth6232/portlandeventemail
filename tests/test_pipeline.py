from dataclasses import replace
from datetime import timezone

import pytest

import pipeline
from config import load_settings
from helpers import at, event
from pipeline import NoSourcesAvailable, assemble, collect, dedupe, group_series
from sources import Source


def _ok(settings, window):
    return [event("Trivia")]


def _broken(settings, window):
    raise ConnectionError("down")


def use_sources(monkeypatch, *sources):
    monkeypatch.setattr(pipeline, "registry", lambda prefs=None: sources)


def test_collect_survives_one_broken_source(monkeypatch, window):
    use_sources(monkeypatch, Source("a", "A", _ok, 1), Source("b", "B", _broken, 0))
    assert [e.name for e in collect(load_settings(require_email=False), window)] == ["Trivia"]


def test_collect_raises_when_everything_fails(monkeypatch, window):
    use_sources(monkeypatch, Source("b", "B", _broken, 0))
    with pytest.raises(NoSourcesAvailable):
        collect(load_settings(require_email=False), window)


def test_collect_skips_sources_without_keys(monkeypatch, window):
    monkeypatch.delenv("TICKETMASTER_API_KEY", raising=False)
    keyed = Source("k", "Keyed", _broken, 0, requires="ticketmaster_api_key")
    use_sources(monkeypatch, keyed, Source("a", "A", _ok, 1))
    assert len(collect(load_settings(require_email=False), window)) == 1


def ticketed(name, start, venue="Moda Center", source="ticketmaster", **kw):
    return event(name, start, venue, source=source, ticketed=True, **kw)


def test_ticketed_duplicates_merge_on_venue_and_time():
    tm = ticketed("Portland Trail Blazers vs. Utah Jazz", at(10, 8), price="$38 to $410")
    sg = ticketed("Utah Jazz at Portland Trail Blazers", at(10, 8), source="seatgeek")
    merged = dedupe([sg, tm])
    assert len(merged) == 1
    assert merged[0].source == "ticketmaster"
    assert merged[0].sources == {"ticketmaster", "seatgeek"}


def test_venue_names_that_contain_each_other_match():
    a = ticketed("Hozier", at(10, 3, 20), venue="Moda Center")
    b = ticketed("Hozier", at(10, 3, 20), venue="Theater of the Clouds, Moda Center", source="seatgeek")
    assert len(dedupe([a, b])) == 1


def test_different_names_at_a_bar_stay_separate():
    a = event("Trivia", at(9, 24), "Alberta Street Pub", source="pdxpipeline")
    b = event("Open Mic", at(9, 24), "Alberta Street Pub", source="parks")
    assert len(dedupe([a, b])) == 2


def test_two_showtimes_from_one_source_are_not_duplicates():
    a = event("Paris, Texas", at(9, 24, 16), "Hollywood Theatre", source="hollywood")
    b = event("Paris, Texas", at(9, 24, 19), "Hollywood Theatre", source="hollywood")
    assert len(dedupe([a, b])) == 2


def test_series_fold_into_first_date():
    weekly = [event("Geeks Who Drink", start, "Alberta Street Pub") for start in (at(9, 29), at(9, 22), at(10, 6))]
    grouped = group_series(weekly)
    assert len(grouped) == 1
    assert grouped[0].start == at(9, 22)
    assert grouped[0].other_dates == [at(9, 29), at(10, 6)]


def test_assemble_places_series_once(window, prefs):
    runs = [event("Paris, Texas", at(9, d), "Hollywood Theatre", source="hollywood", category="Film")
            for d in (22, 23, 24)]
    digest = assemble(runs, window, prefs)
    assert [s.key for s in digest.sections] == ["today"]
    assert len(digest.sections[0].events[0].other_dates) == 2


def test_assemble_keeps_only_listed_venues_and_flags_big_ones(window, prefs):
    events = [
        ticketed("Unknown Band", at(9, 24), venue="Some Tiny Bar"),
        ticketed("The Lemon Twigs", at(9, 24, 21), venue="Doug Fir Lounge"),
        ticketed("Parking: Blazers vs. Jazz", at(9, 24), venue="Moda Center"),
        ticketed("Blazers vs. Jazz", at(9, 24), venue="Moda Center"),
    ]
    digest = assemble(events, window, prefs)
    kept = {e.name: e for s in digest.sections for e in s.events}
    assert set(kept) == {"The Lemon Twigs", "Blazers vs. Jazz"}
    assert kept["Blazers vs. Jazz"].big_venue
    assert not kept["The Lemon Twigs"].big_venue


def test_assemble_converts_utc_before_bucketing(window, prefs):
    # 7pm Tuesday in Portland is 2am Wednesday UTC.
    late = ticketed("Blazers vs. Jazz", at(9, 22, 19).astimezone(timezone.utc))
    digest = assemble([late], window, prefs)
    assert digest.sections[0].key == "today"


def test_assemble_drops_events_outside_window(window, prefs):
    digest = assemble([event("Old", at(9, 21)), event("Far", at(11, 30))], window, prefs)
    assert digest.sections == []
    assert digest.total == 0


def test_source_labels_follow_what_was_shown(window, prefs):
    digest = assemble([event("Trivia", at(9, 22), source="pdxpipeline")], window, prefs)
    assert digest.source_labels == ["PDX Pipeline"]


def test_source_labels_include_the_full_list(window, prefs):
    prefs = replace(prefs, section_limits={**prefs.section_limits, "today": 1})
    films = event("Film", at(9, 22, 19), source="hollywood", category="Film")
    trivia = event("Trivia", at(9, 22, 20), source="pdxpipeline", category="Trivia")
    digest = assemble([films, trivia], window, prefs)
    assert [e.name for e in digest.sections[0].rest] == ["Trivia"]
    assert "PDX Pipeline" in digest.source_labels


def test_an_emails_top_picks_come_from_different_categories(window, prefs):
    # Same two categories in every section: each section still gets its own.
    events = [event(f"{c} {d}", at(9, d, 19), f"Venue {c} {d}", category=c)
              for d in (22, 25, 10 + 30) if d <= 30
              for c in ("Film", "Talks & Readings", "Music")]
    events += [event(f"{c} Oct", at(10, 8, 19), f"Venue {c} Oct", category=c)
               for c in ("Film", "Talks & Readings", "Music")]
    digest = assemble(events, window, prefs)
    picks = [s.pick.category for s in digest.sections if s.pick]
    assert len(picks) == 3 and len(set(picks)) == 3
