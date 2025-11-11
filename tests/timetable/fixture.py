"""Reusable timetable fixtures."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, TypeAlias

import pytest

from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.schedule import Schedule
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.models.session import SecSession
from tests.academics.fixture import CurriculumCourseFactory

AcademicYearFactory: TypeAlias = Callable[[datetime], AcademicYear]
SemesterFactory: TypeAlias = Callable[[int], Semester]
SectionFactory: TypeAlias = Callable[[str, str, int, int], Section]
SecSessionFactory: TypeAlias = Callable[[str, str, str], SecSession]

DEF_DATE = datetime(2010, 9, 1)


@pytest.fixture
def academic_year() -> AcademicYear:
    """Get an Academic_year object."""
    # set the end date by default in one year
    return AcademicYear.objects.create(start_date=DEF_DATE)


@pytest.fixture
def schedule() -> Schedule:
    """Get a Schedule object."""
    return Schedule.get_default(day=1)


def _ensure_semester_statuses() -> None:
    """Make sure default semester statuses exist before creating semesters."""
    SemesterStatus._populate_attributes_and_db()


@pytest.fixture
def semester(academic_year_factory: AcademicYearFactory) -> Semester:
    """Get a Semester object for a specific academic year."""
    _ensure_semester_statuses()
    ay = academic_year_factory(DEF_DATE)
    return Semester.objects.create(academic_year=ay, number=1)


@pytest.fixture
def section(semester, curriculum_course) -> Section:
    return Section.objects.create(
        semester=semester, curriculum_course=curriculum_course, number=1
    )


@pytest.fixture
def session(section, room) -> SecSession:
    return SecSession.objects.create(room=room, section=section)


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


@pytest.fixture
def academic_year_factory() -> AcademicYearFactory:

    def _make(start_date: datetime = DEF_DATE) -> AcademicYear:

        return AcademicYear.objects.create(start_date=start_date)

    return _make


@pytest.fixture
def semester_factory(academic_year_factory: AcademicYearFactory) -> SemesterFactory:
    def _make(number: int, ay_start_date: datetime = DEF_DATE) -> Semester:

        _ensure_semester_statuses()

        ay = academic_year_factory(ay_start_date)

        return Semester.objects.create(academic_year=ay, number=number)

    return _make


@pytest.fixture
def section_factory(
    semester_factory: SemesterFactory,
    curriculum_course_factory: CurriculumCourseFactory,
) -> SectionFactory:
    def _make(
        course_number: str = "111",
        curriculum_short_name: str = "CURRI_TEST",
        number: int = 1,
        semester_number: int = 1,
    ) -> Section:
        semester = semester_factory(semester_number)
        curriculum_course = curriculum_course_factory(
            course_number, curriculum_short_name
        )
        return Section.objects.create(
            curriculum_course=curriculum_course, semester=semester, number=number
        )

    return _make


@pytest.fixture
def session_factory(section_factory: SectionFactory, room_factory) -> SecSessionFactory:
    def _make(
        room_code: str, course_number: str, curriculum_short_name: str
    ) -> SecSession:
        room = room_factory(room_code="007")
        section = section_factory(course_number, curriculum_short_name, 1, 1)
        return SecSession.objects.create(section=section, room=room)

    return _make
