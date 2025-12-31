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

    expected_username = mk_username("Paula", "Ray", prefix_len=2)

    assert faculty.staff_profile is not None
    assert faculty.staff_profile.user.username == expected_username
    assert faculty.staff_profile.staff_id.startswith(faculty.staff_profile.ID_PREFIX)
    assert faculty.college == College.get_default()
