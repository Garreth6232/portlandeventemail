from helpers import at, event
from mailer import render
from pipeline import assemble


def build(events, window, prefs):
    return assemble(events, window, prefs)


def test_html_escapes_source_text(window, prefs):
    digest = build([event("<script>x</script>", category="Film")], window, prefs)
    out = render.html(digest, "Portland Events")
    assert "<script>x" not in out
    assert "&lt;script&gt;" in out


def test_rows_render_in_time_order(window, prefs):
    late = event("Late Film", at(9, 22, 21), category="Film")
    early = event("Early Trivia", at(9, 22, 18), category="Trivia")
    out = render.text(build([late, early], window, prefs), "Portland Events")
    assert out.index("Early Trivia") < out.index("Late Film")


def test_clock_format():
    assert render.clock(at(9, 22, 19)) == "7 pm"
    assert render.clock(at(9, 22, 19, 30)) == "7:30 pm"
    assert render.clock(at(9, 22, 12)) == "noon"
    assert render.clock(at(9, 22, 0)) == "12 am"


def test_more_dates_wording():
    one = event("Trivia", at(9, 22))
    one.other_dates = [at(9, 29)]
    assert render.more_dates(one) == "Also Tue 9/29"

    same_day = event("Film", at(9, 22, 16), category="Film")
    same_day.other_dates = [at(9, 22, 19)]
    assert render.more_dates(same_day) == "Also 7 pm"

    run = event("Film", at(9, 22), category="Film")
    run.other_dates = [at(9, 23), at(9, 24), at(9, 25)]
    assert render.more_dates(run) == "Runs through Fri 9/25, 4 showings"


def test_subject_leads_with_top_pick(window, prefs):
    digest = build([event("Natural Wine Night", category="Food & Drink"),
                    event("Trivia", at(9, 22, 20), category="Trivia")], window, prefs)
    assert render.subject(digest) == "Tue 9/22: Natural Wine Night and 1 more"


def test_empty_digest(window, prefs):
    digest = build([], window, prefs)
    assert "Nothing new on the calendar" in render.html(digest, "Portland Events")
    assert render.subject(digest) == "Tue 9/22: nothing new"


def test_other_category_is_not_shown(window, prefs):
    out = render.text(build([event("Record Swap", venue="Tomorrow Theater", category="Other")], window, prefs), "x")
    assert "Tomorrow Theater\n" in out


def test_venue_is_not_repeated_when_it_matches_the_name(window, prefs):
    market = event("Kenton Farmers Market", venue="Kenton Farmers Market", category="Market")
    out = render.text(build([market], window, prefs), "x")
    assert "Kenton Farmers Market\nMarket\n" in out


def test_copy_has_no_em_dashes(window, prefs):
    out = render.html(build([event("Show", category="Film")], window, prefs), "Portland Events")
    assert "—" not in out and "&mdash;" not in out
