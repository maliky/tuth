"""Test weekdays enum module."""

from app.timetable.choices import WEEKDAYS_NUMBER


def test_monday_is_one():
    assert WEEKDAYS_NUMBER.MONDAY == 1
