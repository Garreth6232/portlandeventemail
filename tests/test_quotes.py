from datetime import date, timedelta

import quotes
from helpers import event
from mailer import render
from pipeline import assemble


def test_same_day_same_quote():
    day = date(2026, 9, 22)
    assert quotes.for_day(day) == quotes.for_day(day)


def test_no_repeats_until_the_list_runs_out():
    start = date(2026, 9, 22)
    seen = [quotes.for_day(start + timedelta(days=i)) for i in range(len(quotes.QUOTES))]
    assert len(set(seen)) == len(quotes.QUOTES)


def test_every_quote_has_words_and_a_source():
    assert all(q.strip() and who.strip() for q, who in quotes.QUOTES)


def test_quote_sits_between_the_date_and_today(window, prefs):
    digest = assemble([event("Film", category="Film")], window, prefs)
    quote, who = quotes.for_day(window.today)
    html = render.html(digest, "x")
    escaped = quote.replace("'", "&#39;")
    assert html.index(render.long_day(window.today)) < html.index(escaped) < html.index(f">{digest.sections[0].title}</span>")
    assert who in html
    text = render.text(digest, "x")
    assert f'"{quote}"' in text and text.index(quote) < text.index(digest.sections[0].title.upper())
