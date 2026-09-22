"""String helpers for matching and displaying event names."""
from __future__ import annotations

import re
from functools import lru_cache

_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")
_ROMAN = re.compile(r"^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")
_FILM_GAUGE = re.compile(r"^\d+MM$")

_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "vs", "with"}
_ACRONYMS = {"DJ", "TV", "PDX", "USA", "NYC", "LA", "UK", "OVA", "MC", "Q&A", "BYOB", "LGBTQ", "NBA", "MLS"}


@lru_cache(maxsize=4096)
def normalize(value: str) -> str:
    """Lowercase, drop punctuation, and collapse whitespace, for comparisons."""
    value = value.lower().replace("&", " and ")
    value = _PUNCT.sub(" ", value)
    value = _SPACE.sub(" ", value).strip()
    if value.startswith("the "):
        value = value[4:]
    return value


def tidy_title(value: str) -> str:
    """Convert an ALL-CAPS title to title case. Anything with lowercase
    letters is left exactly as the source wrote it."""
    value = value.strip()
    letters = [c for c in value if c.isalpha()]
    if len(letters) < 4 or not all(c.isupper() for c in letters):
        return value

    words = value.split()
    out = []
    after_colon = False
    for i, word in enumerate(words):
        core = word.strip("\"'()[]:,.!?")
        if core in _ACRONYMS or _ROMAN.match(core):
            out.append(word)
        elif _FILM_GAUGE.match(core):
            out.append(word.lower())
        elif core.lower() in _SMALL_WORDS and i > 0 and not after_colon:
            out.append(word.lower())
        else:
            out.append("-".join(part.capitalize() for part in word.split("-")))
        after_colon = word.endswith(":")
    return " ".join(out)
