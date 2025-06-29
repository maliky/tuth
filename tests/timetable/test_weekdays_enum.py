"""Test weekdays enum module."""

from app.timetable.choices import WEEKDAYS_NUMBER


def test_monday_is_one():
    assert WEEKDAYS_NUMBER.MONDAY == 1
    assert WEEKDAYS_NUMBER.TUESDAY == 2
    assert WEEKDAYS_NUMBER.WEDNESDAY == 3
    assert WEEKDAYS_NUMBER.THURSDAY == 4
    assert WEEKDAYS_NUMBER.FRIDAY == 5
    assert WEEKDAYS_NUMBER.SATURDAY == 6
    assert WEEKDAYS_NUMBER.SUNDAY == 7
    assert WEEKDAYS_NUMBER.TBA == 0
