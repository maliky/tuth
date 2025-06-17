"""Test Schedule model."""

from datetime import time

import pytest

from app.timetable.models.session import Schedule


@pytest.mark.django_db
def test_schedule_invalid_times():
    """clean() should assert when end_time precedes start_time."""
    sched = Schedule(weekday=1, start_time=time(10, 0), end_time=time(9, 0))
    with pytest.raises(AssertionError, match="start_time must be before end_time"):
        sched.clean()


@pytest.mark.django_db
def test_schedule_valid_times():
    """clean() succeeds when times are ordered correctly."""
    sched = Schedule(weekday=1, start_time=time(8, 0), end_time=time(9, 0))
    sched.clean()
