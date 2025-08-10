"""Tests for unique constraints on RoleAssignment model."""

from datetime import date

import pytest
from django.db import transaction, IntegrityError
from django.contrib.auth.models import Group

from app.people.models.role_assignment import RoleAssignment
from app.shared.auth.perms import UserRole

pytestmark = pytest.mark.django_db


def test_unique_role_per_period(user, college, department):
    """Check that there only one person with the role officer in a periode."""
    start = date.today()
    group_registrar = Group.objects.create(name=UserRole.REGISTRAR_OFFICER.value.group)
    RoleAssignment.objects.create(
        user=user,
        role=group_registrar,
        college=college,
        department=department,
        start_date=start,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RoleAssignment.objects.create(
                user=user,
                role=group_registrar,
                college=college,
                department=department,
                start_date=start,
            )
