"""Reusable timetable fixtures."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

import pytest

from app.academics.models.program import Program
from app.spaces.models.core import Room
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.schedule import Schedule
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import Session


@pytest.fixture
def academic_year() -> AcademicYear:
    # only start_date is mandatory; code & long_name are auto-generated in save()
    return AcademicYear.objects.create(start_date=date(2025, 9, 1))


@pytest.fixture
def semester(academic_year: AcademicYear) -> Semester:
    return Semester.objects.create(
        academic_year=academic_year,
        number=1,
        start_date=academic_year.start_date,
        end_date=date(2026, 1, 15),
    )


@pytest.fixture
def section_factory(
    program: Program, semester: Semester, schedule: Schedule
) -> Callable[[int], Section]:
    def _make(number: int) -> Section:
        return Section.objects.create(
            program=program,
            semester=semester,
            number=number,
            faculty=None,
            start_date=semester.start_date,
            end_date=semester.end_date,
            max_seats=30,
        )

    return _make


@pytest.fixture
def schedule() -> Schedule:
    # Schedule has weekday, start_time, and end_time
    now = datetime.now().time()
    return Schedule.objects.create(weekday=1, start_time=now, end_time=now)


@pytest.fixture
def session(
    section_factory: Callable[[int], Section], room: Room, schedule: Schedule
) -> Session:
    # Session model has FK room, schedule, section
    return Session.objects.create(
        room=room, schedule=schedule, section=section_factory(1)
    )
