"""Test fixtures of people."""

from __future__ import annotations

from typing import Callable, TypeAlias

import pytest
from django.contrib.auth.models import User

from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.donor import Donor
from app.people.models.staffs import Faculty, Staff
from app.people.models.student import Student
from app.timetable.models.semester import Semester

UserFactory: TypeAlias = Callable[[str], User]
StaffFactory: TypeAlias = Callable[[str, Department], Staff]


@pytest.fixture
def superuser() -> User:
    return User.objects.create_superuser(
        username="super", email="super@example.com", password="secret123"
    )


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        username="user_default", email="default@koba.sarl", password="zyx987"
    )


@pytest.fixture
def user_factory() -> UserFactory:
    """Returns a function to create a user."""

    def _make(username: str) -> User:
        return User.objects.create_user(username=username)

    return _make


@pytest.fixture
def staff(user_factory: UserFactory, department: Department) -> Staff:
    """A staff."""
    # Staff requires staff_id
    staff_u = user_factory("mboulot")
    return Staff.objects.create(user=staff_u, staff_id="ST123", department=department)


@pytest.fixture
def staff_factory(user_factory: UserFactory) -> StaffFactory:
    """Return a callable for making extra Staff objects on demand.

    my_staff = staff_factory("joe", some_department)
    """

    def _make(uname: str, department: Department) -> Staff:
        user = user_factory(uname)
        return Staff.objects.create(user=user, department=department)

    return _make


@pytest.fixture
def faculty(staff_factory: StaffFactory, department: Department) -> Faculty:
    """Default Faculty."""
    staff = staff_factory("elprofessor", department)
    return Faculty.objects.create(staff_profile=staff)


@pytest.fixture
def donor(user_factory: UserFactory) -> Donor:
    user = user_factory("legenereux")
    return Donor.objects.create(user=user)


@pytest.fixture
def student(
    user_factory: UserFactory,
    semester: Semester,
    curriculum: Curriculum,
) -> Student:
    user = user_factory("letudiant")
    return Student.objects.create(
        user=user,
        curriculum=curriculum,
        current_enroled_semester=semester,
    )
