"""
Reusable fixtures for reservation-related tests.
Put this file at tests/conftest.py – pytest will auto-discover it.
"""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from app.academics.models import College, Course
from app.people.models import StaffProfile, StudentProfile
from app.timetable.models import AcademicYear, Schedule, Section, Semester

User = get_user_model()


# ─── reference data ──────────────────────────────────────────────────────────
@pytest.fixture
def college():
    return College.objects.create(code="COAS", fullname="College of Arts and Sciences")


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
    return Schedule.objects.create(weekday=1)


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
