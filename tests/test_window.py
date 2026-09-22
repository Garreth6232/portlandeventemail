from datetime import date

from helpers import TZ, at
from models import Window


def test_sections(window):
    assert window.section_for(at(9, 22, 20)) == "today"
    assert window.section_for(at(9, 23, 0)) == "week"
    assert window.section_for(at(9, 29, 23)) == "week"
    assert window.section_for(at(9, 30, 0)) == "later"
    assert window.section_for(at(10, 22, 23)) == "later"
    assert window.section_for(at(10, 23, 0)) is None
    assert window.section_for(at(9, 21, 23)) is None


def test_late_in_the_month_still_looks_ahead():
    # The calendar-month version of this left "Coming Up" empty after the 23rd.
    window = Window(date(2026, 9, 28), TZ)
    assert window.section_for(at(10, 15)) == "later"
