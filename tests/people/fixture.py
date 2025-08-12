"""Test fixtures of people."""

from __future__ import annotations

from typing import Callable, TypeAlias, cast

import pytest
from django.contrib.auth.models import User, Group

from app.people.models.donor import Donor
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from tests.academics.fixture import CurriculumFactory

UserFactory: TypeAlias = Callable[[str], User]
GroupFactory: TypeAlias = Callable[[str], Group]
StaffFactory: TypeAlias = Callable[[str], Staff]
StudentFactory: TypeAlias = Callable[[str, str], Student]
DonorFactory: TypeAlias = Callable[[str], Donor]
FacultyFactory: TypeAlias = Callable[[str], Faculty]


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
def staff() -> Staff:
    """A staff."""
    return cast(
        Staff, Staff.objects.create(user=User(username="mboulot"), staff_id="ST123")
    )


@pytest.fixture
def faculty(staff: Staff) -> Faculty:
    """Default Faculty."""
    fac = Faculty(staff_profile=staff)
    fac.save()
    return fac


@pytest.fixture
def donor(user_factory: UserFactory) -> Donor:
    user = user_factory("donorlegenereux")
    return cast(Donor, Donor.objects.create(user=user))


@pytest.fixture
def student(semester, curriculum) -> Student:
    return cast(
        Student,
        Student.objects.create(
            user=User(username="letudiant"),
            curriculum=curriculum,
            current_enrolled_semester=semester,
        ),
    )


# ~~~~~~~~~~~~~~~~ Factories ~~~~~~~~~~~~~~~~


@pytest.fixture
def group_factory() -> GroupFactory:
    """Returns a function to create a group."""

    def _make(name: str) -> Group:
        return Group.objects.create(name=name)

    return _make


@pytest.fixture
def user_factory() -> UserFactory:
    """Returns a function to create a user."""

    def _make(username: str) -> User:
        return User.objects.create_user(username=username)

    return _make


@pytest.fixture
def staff_factory() -> StaffFactory:
    """Return a callable for making extra Staff objects on demand.

    my_staff = staff_factory("joe", some_department)
    """

    def _make(staff_uname: str) -> Staff:
        return cast(Staff, Staff.objects.create(user=User(username=staff_uname)))

    return _make


@pytest.fixture
def faculty_factory() -> FacultyFactory:
    """Return a callable for making extra Faculty objects on demand.

    my_faculty = faculty_factory("joe", some_department)
    """

    def _make(faculty_uname: str) -> Faculty:
        return cast(Faculty, Faculty.objects.create(username=faculty_uname))

    return _make


@pytest.fixture
def student_factory(
    curriculum_factory: CurriculumFactory,
) -> StudentFactory:
    """Return a callable for making extra Student objects on demand.

    my_student = student_factory("joe", some_curriculum short name)
    """

    def _make(uname: str, curri_short_name: str) -> Student:
        return cast(
            Student,
            Student.objects.create(
                user=User(username=uname),
                curriculum=curriculum_factory(curri_short_name),
            ),
        )

    return _make


@pytest.fixture
def donor_factory() -> DonorFactory:
    """Return a callable for making extra Donoro objects on demand."""

    def _make(uname: str) -> Donor:
        return cast(
            Donor,
            Donor.objects.create(
                user=User(username=uname),
            ),
        )

    return _make
