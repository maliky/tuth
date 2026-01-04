"""Concrete creation test for Faculty."""

import pytest

from app.academics.models.college import College
from app.people.models.faculty import Faculty
from app.people.utils import mk_username


@pytest.mark.django_db
def test_faculty_get_or_create() -> None:
    faculty = Faculty.objects.create(
        first_name="Paula",
        last_name="Ray",
    )

    expected_username = mk_username("Paula", "Ray")

    assert faculty.staff_profile is not None
    assert faculty.staff_profile.user.username == expected_username
    assert faculty.staff_profile.staff_id.startswith(faculty.staff_profile.ID_PREFIX)
    assert faculty.college == College.get_default()


@pytest.mark.django_db
def test_faculty_college_assignation(college_factory):
    college = college_factory("TEST")

    faculty = Faculty.objects.create(
        first_name="Cecilia", last_name="Danao", college=college
    )
    assert faculty.college.code == "TEST", f"{faculty.college}"


@pytest.mark.django_db
def test_faculty_creation_ensures_unique_username() -> None:
    first = Faculty.objects.create(first_name="Amaury", last_name="Smith")
    second = Faculty.objects.create(first_name="Ambroise", last_name="Smith")

    assert (
        first.staff_profile.user.username != second.staff_profile.user.username
    ), f"{first.staff_profile.user.username}  {second.staff_profile.user.username}"
    assert (
        second.staff_profile.user.username == first.staff_profile.user.username + "2"
    ), f"second={second.staff_profile.user.username}, first={first.staff_profile.user.username}"
