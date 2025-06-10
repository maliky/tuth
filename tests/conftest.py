"""
Reusable fixtures for reservation-related tests.
pytest auto-discover it.
"""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from app.academics.models import College, Course
from app.people.models.profile import StaffProfile, StudentProfile
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import Session

User = get_user_model()


# ─── reference data ──────────────────────────────────────────────────────────
@pytest.fixture
def college():
    return College.objects.create(code="COAS", long_name="College of Arts and Sciences")


@pytest.fixture
def course(college):
    return Course.objects.create(
        name="TEST",
        number="101",
        title="Course",
        credit_hours=3,
        college=college,
    )


@pytest.fixture
def academic_year():
    return AcademicYear.objects.create(
        start_date=date(2025, 9, 1),
        end_date=date(2026, 8, 31),
    )


@pytest.fixture
def semester(academic_year):
    return Semester.objects.create(
        academic_year=academic_year,
        number=1,
        start_date=date(2025, 9, 1),
        end_date=date(2026, 1, 15),
    )


@pytest.fixture
def schedule():
    return Session.objects.create(weekday=1)


# ─── user / profile helpers ──────────────────────────────────────────────────
@pytest.fixture
def student_user():
    return User.objects.create(username="student")


@pytest.fixture
def student_profile(student_user):
    return StudentProfile.objects.create(
        user=student_user,
        student_id="S123456",
        enrollment_semester=1,
    )


@pytest.fixture
def staff_profile():
    user = User.objects.create(username="staff")
    return StaffProfile.objects.create(user=user, staff_id="ST123")


# ─── section factory ─────────────────────────────────────────────────────────
@pytest.fixture
def section_factory(course, semester, schedule):
    """
    Usage:
        sec = section_factory(3)      # number=3
    """

    def _make(number: int):
        return Section.objects.create(
            course=course,
            semester=semester,
            schedule=schedule,
            number=number,
            max_seats=30,
        )

    return _make


@pytest.fixture
def superuser(db):
    User = get_user_model()
    return User.objects.create_superuser(
        username="super", email="super@example.com", password="secret123"
    )


# ─── generic factories ------------------------------------------------------
@pytest.fixture
def college_factory():
    """Return helper to create colleges on demand."""

    def _make(code: str = "COAS"):
        return College.objects.create(code=code)
    return _make


@pytest.fixture
def course_factory(college_factory):
    """Return helper to create courses linked to a college."""

    def _make(
        name: str = "TEST",
        number: str = "101",
        title: str = "Course",
        credit_hours: int = 3,
        college=None,
    ):
        if college is None:
            college = college_factory()
        return Course.objects.create(
            name=name,
            number=number,
            title=title,
            credit_hours=credit_hours,
            college=college,
        )

    return _make
