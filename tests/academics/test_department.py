"""Tests for the Academic Department module."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.department import Department

pytestmark = pytest.mark.django_db


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_department_unique_short_name_in_college(college, department_factory):
    """In a College a department short_name should be unique."""

    department_factory("GEN")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Department.objects.create(short_name="GEN", college=college)
