"""
Reusable fixtures for reservation-related tests.
pytest auto-discover it.
"""
# conftest.py
from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Optional

import pytest
from django.contrib.auth.models import User

from app.academics.models.college import College
from app.academics.models.course import Course
from app.people.models.others import Student
from app.people.models.staffs import Faculty, Staff
from app.academics.models.department import Department
from app.spaces.models.core import Room, Space
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import Schedule, Session

# ─── reference data ───────────────────────────────────────────

@pytest.fixture
def college() -> College:
    # field is `long_name`, not `fullname`
    return College.objects.create(code="COAS", long_name="College of Arts and Sciences")


@pytest.fixture
def course(college: College) -> Course:
    return Course.objects.create(
        name="TEST",
        number="101",
        title="Course",
        credit_hours=3,
        college=college,
    )


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
def space() -> Space:
    # model is Space with fields `code` and `full_name`
    return Space.objects.create(code="AA", full_name="Academic Annex")


@pytest.fixture
def room(space: Space) -> Room:
    # Room has fields `code` and FK `space`
    return Room.objects.create(code="101", space=space)


@pytest.fixture
def schedule() -> Schedule:
    # Schedule has `weekday`, `start_time`, and `end_time`
    now = datetime.now().time()
    return Schedule.objects.create(weekday=1, start_time=now, end_time=now)


# ─── section factory ───────────────────────────────────────────

@pytest.fixture
def section_factory(
    course: Course, semester: Semester, schedule: Schedule
) -> Callable[[int], Section]:
    def _make(number: int) -> Section:
        return Section.objects.create(
            course=course,
            semester=semester,
            number=number,
            faculty=None,
            start_date=semester.start_date,
            end_date=semester.end_date,
            max_seats=30,
            schedule=schedule,
        )

    return _make


@pytest.fixture
def session(
    section_factory: Callable[[int], Section], room: Room, schedule: Schedule
) -> Session:
    # Session model has FK `room`, `schedule`, `section`
    return Session.objects.create(
        room=room, schedule=schedule, section=section_factory(1)
    )


# ─── user / profile helpers ─────────────────────────────────────

@pytest.fixture
def student_user() -> User:
    return User.objects.create_user(username="student")


@pytest.fixture
def student_profile(student_user: User, semester: Semester) -> Student:
    # Student fields: user, student_id, college (nullable), curriculum (nullable),
    # enrollment_semester, enrollment_date (nullable)
    return Student.objects.create(
        user=student_user,
        student_id="S123456",
        enrollment_semester=semester,
    )


@pytest.fixture
def department_factory(college_factory: Callable[[str], College]) -> Callable[..., Department]:
    def _factory(code: str = "GEN", college: Optional[College] = None) -> Department:
        college_obj = college if (college := college) else college_factory()
        return Department.objects.create(code=code, college=college_obj)

    return _factory


@pytest.fixture
def staff_profile(department_factory: Callable[..., Department]) -> Staff:
    # Staff requires `staff_id`
    user = User.objects.create_user(username="staff")
    dept = department_factory()
    return Staff.objects.create(user=user, staff_id="ST123", department=dept)


@pytest.fixture
def faculty_profile(college: College) -> Faculty:
    # Faculty inherits Staff and adds `staff_id` plus optional fields
    # Reuse staff_profile but override college
    user = User.objects.create_user(username="faculty")
    return Faculty.objects.create(user=user, staff_id="FP001", college=college)


@pytest.fixture
def superuser() -> User:
    return User.objects.create_superuser(
        username="super", email="super@example.com", password="secret123"
    )


# ─── generic factories ───────────────────────────────────────────

@pytest.fixture
def college_factory() -> Callable[..., College]:
    def _factory(code: str = "COAS", long_name: Optional[str] = None) -> College:
        """Create ``College`` with matching ``code`` and ``long_name``."""
        return College.objects.create(code=code, long_name=long_name or code)

    return _factory


@pytest.fixture
def course_factory(college_factory: Callable[[str], College]) -> Callable[..., Course]:
    def _factory(
        name: str = "TEST",
        number: str = "101",
        title: str = "Course",
        credit_hours: int = 3,
        college: Optional[College] = None,
    ) -> Course:
        college_obj = college if (college := college) else college_factory()
        return Course.objects.create(
            name=name,
            number=number,
            title=title,
            credit_hours=credit_hours,
            college=college_obj,
        )

    return _factory


