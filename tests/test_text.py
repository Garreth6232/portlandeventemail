from categories import canonical
from text import normalize, tidy_title


def test_normalize():
    assert normalize("The Doug Fir Lounge!") == "doug fir lounge"
    assert normalize("Food & Drink") == "food and drink"


def test_tidy_title_only_touches_all_caps():
    assert tidy_title("NEVER AFTER DARK") == "Never After Dark"
    assert tidy_title("THE THING IN 70MM") == "The Thing in 70mm"
    assert tidy_title("ROCKY II") == "Rocky II"
    assert tidy_title("Hellavision Television – DANCE EVERYWHERE") == "Hellavision Television – DANCE EVERYWHERE"
    assert tidy_title("M") == "M"


def test_canonical_categories():
    assert canonical("Arts & Theatre") == "Theater & Arts"
    assert canonical("broadway_tickets_national") == "Theater & Arts"
    assert canonical("nba") == "Sports"
    assert canonical("Movie") == "Film"
    assert canonical("knitting circle") == "Knitting Circle"
    assert canonical(None) is None
