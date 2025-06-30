"""Test fixtures of people."""

from __future__ import annotations

from typing import Callable, TypeAlias

import pytest
from django.contrib.auth.models import User

from app.people.models.donor import Donor
from app.people.models.staffs import Faculty, Staff
from app.people.models.student import Student
from tests.academics.fixture import CurriculumFactory

UserFactory: TypeAlias = Callable[[str], User]
StaffFactory: TypeAlias = Callable[[str], Staff]
StudentFactory: TypeAlias = Callable[[str, str], Student]
DonorFactory: TypeAlias = Callable[[str], Donor]


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
def staff(user_factory: UserFactory) -> Staff:
    """A staff."""
    # Staff requires staff_id
    staff_u = user_factory("mboulot")
    return Staff.objects.create(user=staff_u, staff_id="ST123")


@pytest.fixture
def faculty(staff_factory: StaffFactory) -> Faculty:
    """Default Faculty."""
    staff = staff_factory("elprofessor")
    return Faculty.objects.create(staff_profile=staff)


@pytest.fixture
def donor(user_factory: UserFactory) -> Donor:
    user = user_factory("donorlegenereux")
    return Donor.objects.create(user=user)


@pytest.fixture
def student(user_factory: UserFactory, semester, curriculum) -> Student:
    user = user_factory("letudiant")
    return Student.objects.create(
        user=user, curriculum=curriculum, current_enroled_semester=semester
    )


# ~~~~~~~~~~~~~~~~ Factories ~~~~~~~~~~~~~~~~


@pytest.fixture
def user_factory() -> UserFactory:
    """Returns a function to create a user."""

    def _make(username: str) -> User:
        return User.objects.create_user(username=username)

    return _make


@pytest.fixture
def staff_factory(user_factory: UserFactory) -> StaffFactory:
    """Return a callable for making extra Staff objects on demand.

    my_staff = staff_factory("joe", some_department)
    """

    def _make(staff_uname: str) -> Staff:

        return Staff.objects.create(user=user_factory(staff_uname))

    return _make


@pytest.fixture
def student_factory(
    user_factory: UserFactory, curriculum_factory: CurriculumFactory
) -> StudentFactory:
    """Return a callable for making extra Student objects on demand.

    my_student = student_factory("joe", some_curriculum short name)
    """

    def _make(uname: str, curri_short_name: str) -> Student:
        return Student.objects.create(
            user=user_factory(uname),
            curriculum=curriculum_factory(curri_short_name),
        )

    return _make


@pytest.fixture
def donor_factory(user_factory: UserFactory) -> DonorFactory:
    """Return a callable for making extra Donoro objects on demand."""

    def _make(uname: str) -> Donor:
        return Donor.objects.create(
            user=user_factory(uname),
        )

    return _make
