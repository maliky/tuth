"""Tests for unique constraints on RoleAssignment model."""

from datetime import date

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from app.people.models.role_assignment import RoleAssignment
from app.shared.auth.perms import UserRole

pytestmark = pytest.mark.django_db


def test_unique_role_per_period(user, college, department):
    """Check that there only one person with the role officer in a periode."""
    start = date.today()
    group_registrar = UserRole.REGISTRAR_OFFICER.value.group
    RoleAssignment.objects.create(
        user=user,
        group=group_registrar,
        college=college,
        department=department,
        start_date=start,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RoleAssignment.objects.create(
                user=user,
                group=group_registrar,
                college=college,
                department=department,
                start_date=start,
            )


def test_enrollment_officer_group_has_permissions():
    """load_roles creates Enrollment Officer group with student perms."""
    call_command("load_roles")
    grp = UserRole.ENROLLMENT_OFFICER.value.group
    codenames = set(grp.permissions.values_list("codename", flat=True))
    assert "view_student" in codenames
    assert "add_student" in codenames
