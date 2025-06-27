"""Tests for unique constraints on RoleAssignment model."""

from datetime import date

import pytest
from django.db import IntegrityError

from app.people.models.role_assignment import RoleAssignment
from app.people.choices import UserRole

pytestmark = pytest.mark.django_db


def test_unique_role_per_period(user, college):
    start = date.today()
    RoleAssignment.objects.create(user=user, role=UserRole.REGISTRAR, college=college, start_date=start)
    with pytest.raises(IntegrityError):
        RoleAssignment.objects.create(user=user, role=UserRole.REGISTRAR, college=college, start_date=start)

