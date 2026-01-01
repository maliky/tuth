"""Concrete creation tests for Staff."""

import pytest

from app.people.models.staffs import Staff
from app.people.utils import mk_username


@pytest.mark.django_db
def test_staff_creation_generates_username_when_missing() -> None:
    staff = Staff.objects.create(
        first_name="Tina",
        last_name="Doe",
    )

    expected_username = mk_username("Tina", "Doe", prefix_len=2)
    assert (
        staff.user.username == expected_username
    ), f"{staff.user.username} != {expected_username}"
    assert staff.staff_id.startswith(Staff.ID_PREFIX)
    assert staff.user.groups.filter(name=Staff.GROUP).exists()


@pytest.mark.django_db
def test_staff_creation_can_set_custom_username() -> None:
    staff = Staff.objects.create(
        username="custom_staff",
        first_name="Tina",
        last_name="Doe",
    )

    assert staff.user.username == "custom_staff", f"{staff.user.username}"
    assert staff.user.first_name == "Tina", f"{staff.user.first_name}"
    assert staff.user.last_name == "Doe", f"{staff.user.last_name}"


@pytest.mark.django_db
def test_staff_creation_ensures_unique_username() -> None:
    first = Staff.objects.create(first_name="Amaury", last_name="Smith")
    second = Staff.objects.create(first_name="Ambroise", last_name="Smith")

    assert (
        first.user.username != second.user.username
    ), f"{first.user.username}  {second.user.username}"
    assert (
        second.user.username == first.user.username + "2"
    ), f"second={second.user.username}, first={first.user.username}"
