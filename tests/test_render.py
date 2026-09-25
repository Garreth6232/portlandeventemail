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


def test_subject_rotates_by_day(window, prefs):
    digest = build([event("Show", category="Film")], window, prefs)
    lines = ("A {date}", "B {weekday}")
    assert render.subject(digest, lines, by_day={}) in {"A Tuesday, Sep 22", "B Tuesday"}
    # Same day, same line, so a re-run doesn't change it.
    assert render.subject(digest, lines, by_day={}) == render.subject(digest, lines, by_day={})


def test_subject_day_override(window, prefs):
    digest = build([], window, prefs)
    assert render.subject(digest, ("x",), by_day={"tuesday": "Taco Tuesday, Portland!"}) == "Taco Tuesday, Portland!"


def test_preferences_subjects_all_format(prefs):
    for line in prefs.subject_lines + tuple(prefs.subject_by_day.values()):
        assert "{" not in line.format(date="Tuesday, Sep 22", weekday="Tuesday")


def test_preheader_names_the_best_listings(window, prefs):
    digest = build([event("Natural Wine Night", category="Food & Drink"),
                    event("Trivia", at(9, 22, 20), category="Trivia")], window, prefs)
    assert "Today: Natural Wine Night and Trivia" in render.html(digest, "x")


def test_empty_digest(window, prefs):
    digest = build([], window, prefs)
    assert "Nothing new on the calendar" in render.html(digest, "Portland Events")


def test_labels_colors_and_top_pick(window, prefs):
    events = [event("Film Night", category="Film", price="Free"),
              event("Dinner", at(9, 22, 18), category="Food & Drink", price="$20"),
              event("Trivia", at(9, 22, 20), category="Trivia")]
    out = render.html(build(events, window, prefs), "x")
    assert render.CATEGORY_COLORS["Film"] in out
    assert "Top pick" in out and out.count("Top pick") == 1
    digest = build(events, window, prefs)
    pick = digest.sections[0].pick
    assert f"{pick.category} · Top pick" in render.text(digest, "x")


def test_free_is_highlighted():
    assert render.is_free("Free") and render.is_free("Free ($5 suggested donation)")
    assert not render.is_free("$20") and not render.is_free(None)


def test_venue_is_not_repeated_when_it_matches_the_name(window, prefs):
    market = event("Kenton Farmers Market", venue="Kenton Farmers Market", category="Market")
    out = render.text(build([market], window, prefs), "x")
    assert "Kenton Farmers Market\nhttps://" in out


def test_other_category_is_not_shown(window, prefs):
    out = render.text(build([event("Record Swap", venue="Tomorrow Theater", category="Other")], window, prefs), "x")
    assert "Tomorrow Theater\n" in out


def test_copy_has_no_em_dashes(window, prefs):
    out = render.html(build([event("Show", category="Film")], window, prefs), "Portland Events")
    assert "—" not in out and "&mdash;" not in out


def _crowded_week(n):
    return [event(f"Trivia {i}", at(9, 23 + i % 5, 18 + i % 4), category="Trivia", venue=f"Bar {i}")
            for i in range(n)]


def test_leftovers_are_listed_at_the_bottom(window, prefs):
    digest = build(_crowded_week(20), window, prefs)
    week = next(s for s in digest.sections if s.key == "week")
    out = render.html(digest, "x")
    assert 'href="#more-week"' in out and 'id="more-week"' in out
    assert f"Plus {week.overflow} more this week, listed at the bottom." in out
    for e in week.rest:
        assert e.name in out
    assert "ALSO THIS WEEK" in render.text(digest, "x")


def test_full_list_is_trimmed_to_stay_under_gmails_clip(window, prefs, monkeypatch):
    digest = build(_crowded_week(60), window, prefs)
    full = render.html(digest, "x")
    monkeypatch.setattr(render, "HTML_BUDGET", len(full.encode()) - 2000)
    trimmed = render.html(digest, "x")
    assert len(trimmed.encode()) <= render.HTML_BUDGET
    assert "more." in trimmed and "And " in trimmed


def test_no_full_list_when_everything_fits(window, prefs):
    out = render.html(build([event("Film", category="Film")], window, prefs), "x")
    assert "The full list" not in out
