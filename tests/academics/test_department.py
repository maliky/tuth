"""Tests for the Academic Department module."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.department import Department

pytestmark = pytest.mark.django_db


def test_department_crud(college):
    """Test Create Read Update Delete operation on Department Model."""
    # create
    dept = Department.objects.create(
        short_name="MATH", long_name="Mathematics", college=college
    )
    assert Department.objects.filter(pk=dept.pk).exists()

    # read
    fetched = Department.objects.get(pk=dept.pk)
    assert fetched == dept

    # update
    assert fetched.long_name != "Applied Mathematics"

    fetched.long_name = "Applied Mathematics"
    fetched.save()
    updated = Department.objects.get(pk=dept.pk)
    assert updated.long_name == "Applied Mathematics"

    # delete
    updated.delete()
    assert not Department.objects.filter(pk=updated.pk).exists()
    assert not Department.objects.filter(pk=dept.pk).exists()
    assert not Department.objects.filter(pk=fetched.pk).exists()


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_department_unique_short_name_in_college(college):
    """In a College a department short_name should be unique."""

    Department.objects.create(short_name="GEN", college=college)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Department.objects.create(short_name="GEN", college=college)
