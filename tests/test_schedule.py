from datetime import datetime, time, timezone

import pytest

import main
from config import SEND_FROM, SEND_UNTIL, TIMEZONE
from main import should_send


def utc(y, m, d, h, minute=0):
    return datetime(y, m, d, h, minute, tzinfo=timezone.utc)


def sends(moment):
    return should_send(moment, TIMEZONE, SEND_FROM, SEND_UNTIL)


def test_window_opens_at_7_45_in_summer():
    tuesday = (2026, 9, 22)
    assert not sends(utc(*tuesday, 14, 44))  # 7:44am PDT
    assert sends(utc(*tuesday, 14, 45))      # 7:45am PDT
    assert sends(utc(*tuesday, 15, 7))       # 8:07am PDT


def test_window_opens_at_7_45_in_winter():
    tuesday = (2026, 12, 1)
    assert not sends(utc(*tuesday, 15, 37))  # 7:37am PST
    assert sends(utc(*tuesday, 16, 7))       # 8:07am PST


def test_late_run_still_sends_before_noon():
    # GitHub picked up a run at 11:42am PDT.
    assert sends(utc(2026, 9, 22, 18, 42))


def test_nothing_after_noon():
    assert not sends(utc(2026, 9, 22, 19, 0))    # noon PDT
    assert not sends(utc(2026, 12, 1, 20, 7))    # 12:07pm PST


def test_weekends_never_send():
    assert not sends(utc(2026, 9, 26, 15))  # Saturday 8am PDT
    assert not sends(utc(2026, 9, 27, 15))  # Sunday


def test_every_scheduled_run_falls_on_the_same_pacific_weekday():
    # The cron runs 10:07 to 19:37 UTC, Monday to Friday. All of those are
    # the same weekday in Portland, winter or summer.
    for day in ((2026, 9, 21), (2026, 12, 7)):
        for hour in (10, 19):
            moment = utc(*day, hour, 37)
            assert moment.astimezone(TIMEZONE).weekday() == moment.weekday()


def test_already_sent_skips_before_building(monkeypatch):
    monkeypatch.setenv("ALREADY_SENT", "true")
    monkeypatch.setenv("GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "x")
    monkeypatch.setenv("RECIPIENTS", "a@x.com")
    monkeypatch.setattr(main, "build_digest", lambda *a: pytest.fail("should not build"))
    assert main.main([]) == 0


def test_mark_sent_writes_the_step_output(monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    main._mark_sent()
    assert out.read_text() == "sent=true\n"
