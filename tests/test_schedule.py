from datetime import datetime, timezone

from config import TIMEZONE
from main import should_send

SUMMER = "0 15 * * 1-5"
WINTER = "0 16 * * 1-5"


def utc(y, m, d, h, minute=0):
    return datetime(y, m, d, h, minute, tzinfo=timezone.utc)


def test_summer_sends_from_the_15_utc_run_only():
    tuesday = (2026, 9, 22)
    assert should_send(utc(*tuesday, 15), TIMEZONE, 8, SUMMER)
    assert not should_send(utc(*tuesday, 16), TIMEZONE, 8, WINTER)


def test_winter_sends_from_the_16_utc_run_only():
    tuesday = (2026, 12, 1)
    assert should_send(utc(*tuesday, 16), TIMEZONE, 8, WINTER)
    assert not should_send(utc(*tuesday, 15), TIMEZONE, 8, SUMMER)


def test_late_start_still_sends():
    # GitHub picked up the 15:00 run at 16:40 UTC (9:40am PDT).
    assert should_send(utc(2026, 9, 22, 16, 40), TIMEZONE, 8, SUMMER)


def test_weekends_never_send():
    saturday = utc(2026, 9, 26, 15)
    assert not should_send(saturday, TIMEZONE, 8, SUMMER)
    assert not should_send(saturday, TIMEZONE, 8, None)


def test_without_a_schedule_uses_the_wall_clock():
    assert should_send(utc(2026, 9, 22, 15, 5), TIMEZONE, 8, None)   # 8:05am PDT
    assert not should_send(utc(2026, 9, 22, 17), TIMEZONE, 8, None)  # 10am PDT
