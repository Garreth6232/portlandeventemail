"""Maps each source's category labels onto one shared set, so a single
weight in preferences.toml applies no matter where an event came from."""
from __future__ import annotations

from typing import Iterable, Optional

FILM = "Film"
FOOD_DRINK = "Food & Drink"
MUSIC = "Music"
COMEDY = "Comedy"
ARTS = "Theater & Arts"
TALKS = "Talks & Readings"
SPORTS = "Sports"
PARKS = "Parks"
MARKET = "Market"
FESTIVAL = "Festival"
FAMILY = "Family"
TRIVIA = "Trivia"
HAPPY_HOUR = "Happy Hour"
VOLUNTEER = "Volunteer"
OTHER = "Other"

_ALIASES = {
    FILM: ["film", "films", "movie", "movies", "cinema", "screening", "screenings & experiences"],
    FOOD_DRINK: ["food & drink", "food and drink", "food", "drink", "drinks", "wine", "beer",
                 "cocktails", "tasting", "winemaker dinner"],
    MUSIC: ["music", "concert", "concerts", "live music", "dj", "band", "classical", "jazz"],
    COMEDY: ["comedy", "stand up", "stand-up", "improv"],
    ARTS: ["arts & theatre", "arts and theatre", "theatre", "theater", "broadway tickets national",
           "broadway", "art", "arts", "dance", "drag", "burlesque", "exhibition", "exhibitions"],
    TALKS: ["talks & readings", "readings & talks", "literary", "reading", "readings", "lecture",
            "lectures", "author", "books"],
    SPORTS: ["sports", "nba", "wnba", "nhl", "mls", "nwsl", "hockey", "soccer", "basketball",
             "ncaa football", "ncaa basketball", "minor league baseball", "baseball", "football"],
    PARKS: ["parks", "parks & rec", "outdoors", "nature", "garden"],
    MARKET: ["market", "markets", "farmers market", "bazaar"],
    FESTIVAL: ["festival", "festivals", "fair"],
    FAMILY: ["family", "kids"],
    TRIVIA: ["trivia", "quiz"],
    HAPPY_HOUR: ["happy hour"],
    VOLUNTEER: ["volunteer"],
    OTHER: ["miscellaneous", "undefined", "other"],
}
_LOOKUP = {alias: label for label, aliases in _ALIASES.items() for alias in aliases}

# For sources whose own labels are missing or too vague, words in the title
# decide. Order matters: the first group with a match wins.
_TITLE_WORDS = (
    (("movie", "film", "cinema", "screening", "35mm", "70mm"), FILM),
    (("trivia", "quiz night"), TRIVIA),
    (("comedy", "stand-up", "improv"), COMEDY),
    (("wine", "tasting", "winemaker", "brewery", "beer", "cider"), FOOD_DRINK),
    (("concert", "live music", "band", "orchestra", "symphony", " dj "), MUSIC),
    (("reading", "author", "lecture", "in conversation", "book launch"), TALKS),
    (("volunteer", "clean-up", "cleanup", "restoration", "weed pull"), VOLUNTEER),
    (("farmers market", "market", "bazaar"), MARKET),
    (("festival", "fair"), FESTIVAL),
)


def canonical(raw: Optional[str]) -> Optional[str]:
    """Shared label for a source's category. Unknown labels pass through,
    title-cased, and rank with the neutral default weight."""
    if not raw:
        return None
    key = raw.replace("_", " ").strip().lower()
    return _LOOKUP.get(key) or key.title()


def known(raw: Optional[str]) -> Optional[str]:
    """Shared label only if the source's label is one we recognize."""
    if not raw:
        return None
    label = _LOOKUP.get(raw.replace("_", " ").strip().lower())
    return None if label == OTHER else label


def infer(title: str, labels: Iterable[str] = (), default: str = OTHER) -> str:
    """Best category from a source's own labels, then the title, then a default."""
    for raw in labels:
        if label := known(raw):
            return label
    text = f" {title.lower()} "
    return next((label for words, label in _TITLE_WORDS if any(w in text for w in words)), default)
