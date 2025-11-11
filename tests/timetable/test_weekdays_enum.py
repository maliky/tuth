"""Test weekdays enum module."""
from app.timetable.choices import WEEKDAYS_NUMBER


def test_monday_is_one():
    assert WEEKDAYS_NUMBER.MONDAY.value == 1
    assert WEEKDAYS_NUMBER.TUESDAY.value == 2
    assert WEEKDAYS_NUMBER.WEDNESDAY.value == 3
    assert WEEKDAYS_NUMBER.THURSDAY.value == 4
    assert WEEKDAYS_NUMBER.FRIDAY.value == 5
    assert WEEKDAYS_NUMBER.SATURDAY.value == 6
    assert WEEKDAYS_NUMBER.SUNDAY.value == 7
    assert WEEKDAYS_NUMBER.TBA.value == 0
