"""Test faculty helper module."""

import pytest
from django.contrib.auth.models import User


from app.people.models.profiles import _ensure_faculty, Faculty
from app.shared.constants import TEST_PW


@pytest.mark.django_db
def test_ensure_faculty_creates_user_and_profile(college_factory):
    col = college_factory(code="COAS", fullname="College of Arts")

    prof = _ensure_faculty("Jane Doe", col)

    assert prof.college == col
    user = prof.user
    assert user.username == "j.doe"
    assert user.first_name == "Jane"
    assert user.last_name == "Doe"
    assert user.check_password(TEST_PW)

    assert User.objects.exclude(username="AnonymousUser").count() == 1
    assert Faculty.objects.count() == 1


@pytest.mark.django_db
def test_ensure_faculty_is_idempotent(college_factory):
    col = college_factory(code="COAS", fullname="College of Arts")
    prof1 = _ensure_faculty("Jane Doe", col)
    prof2 = _ensure_faculty("Jane Doe", col)

    assert prof1.id == prof2.id
    assert User.objects.exclude(username="AnonymousUser").count() == 1
    assert Faculty.objects.count() == 1
