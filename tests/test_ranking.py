from collections import Counter
from dataclasses import replace

import pytest

from helpers import at, event
from ranking import pick, score


def test_category_weight(prefs):
    assert score(event(category="Film"), prefs) > score(event(category="Trivia"), prefs)


def test_unknown_category_is_neutral(prefs):
    assert score(event("Plain", category="Knitting"), prefs) == 1.0


def test_keyword_boosts_use_the_largest_match_only(prefs):
    prefs = replace(prefs, keyword_boosts={"wine": 0.5, "tasting": 0.3}, favorite_venues=())
    both = event("Wine Tasting", category="Other")
    wine = event("Wine Night", category="Other")
    assert score(both, prefs) == score(wine, prefs)


def test_keywords_match_whole_words(prefs):
    prefs = replace(prefs, keyword_boosts={"wine": 0.5}, favorite_venues=())
    assert score(event("Swine Flu Lecture", category="Other"), prefs) == score(event("Lecture", category="Other"), prefs)


def test_favorite_venue_boost(prefs):
    fav = event("Movie", venue="Hollywood Theatre", category="Film")
    other = event("Movie", venue="Regal Fox Tower", category="Film")
    assert score(fav, prefs) - score(other, prefs) == pytest.approx(prefs.venue_boost)


def test_extra_sources_add_confirmation(prefs):
    one = event("Show")
    two = event("Show")
    two.sources.add("seatgeek")
    assert score(two, prefs) > score(one, prefs)


def test_big_venue_cap(prefs):
    prefs = replace(prefs, max_big=1)
    games = [event(f"Game {i}", at(9, 22), "Moda Center", category="Sports", big_venue=True) for i in range(3)]
    chosen, overflow = pick(games + [event("Trivia", category="Trivia")], limit=5, prefs=prefs)
    assert sum(e.big_venue for e in chosen) == 1
    assert len(chosen) == 2 and overflow == 2


def test_category_cap_spreads_a_section(prefs):
    prefs = replace(prefs, max_per_category=2)
    films = [event(f"Film {i}", category="Film") for i in range(6)]
    others = [event("Tasting", category="Food & Drink"), event("Show", category="Music"),
              event("Market", category="Market")]
    chosen, _ = pick(films + others, limit=5, prefs=prefs)
    counts = Counter(e.category for e in chosen)
    assert counts["Film"] == 2
    assert {"Food & Drink", "Music", "Market"} <= set(counts)


def test_category_cap_does_not_leave_seats_empty(prefs):
    prefs = replace(prefs, max_per_category=2)
    films = [event(f"Film {i}", category="Film") for i in range(6)]
    chosen, overflow = pick(films, limit=4, prefs=prefs)
    assert len(chosen) == 4 and overflow == 2


def test_chosen_come_back_best_first(prefs):
    low = event("Volunteer", category="Volunteer")
    high = event("Film", category="Film")
    chosen, _ = pick([low, high], limit=2, prefs=prefs)
    assert [e.name for e in chosen] == ["Film", "Volunteer"]
