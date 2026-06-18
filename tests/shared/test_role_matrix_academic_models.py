"""Academic role-matrix expectations."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from app.shared.auth.perms import UserRole

pytestmark = pytest.mark.django_db


def _group_codenames(role: UserRole) -> set[str]:
    """Return permission codenames loaded onto one role group."""
    return set(role.value.group.permissions.values_list("codename", flat=True))


def test_academic_leaders_unlink_program_courses_without_deleting_catalog_courses():
    """Program removal should delete CurriCrs links, not Course catalog records."""
    call_command("load_roles", verbosity=0)

    for role in (UserRole.CHAIR, UserRole.DEAN, UserRole.VPAA):
        codenames = _group_codenames(role)
        assert "delete_curricrs" in codenames
        assert "delete_course" not in codenames
