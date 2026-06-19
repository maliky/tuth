"""Tests for the read-only MWE checker command."""

from __future__ import annotations

from datetime import date
from io import StringIO

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command

from app.shared.management.commands.check_mwe import RUNTIME_USERS
from app.shared.management.commands.create_test_users import TEST_PASSWORD
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus

pytestmark = pytest.mark.django_db


def _runtime_usernames() -> set[str]:
    """Return canonical runtime usernames from the MWE checker."""
    return {username for username, _group_name in RUNTIME_USERS}


def test_check_mwe_uses_canonical_reg_officer_username() -> None:
    """The documented Registrar Officer runtime account should match role code."""
    usernames = _runtime_usernames()

    assert "test_reg_officer" in usernames
    assert "test_registrar_officer" not in usernames


def test_check_mwe_warn_only_reports_missing_users() -> None:
    """Warn-only mode should report missing accounts without raising."""
    stdout = StringIO()

    call_command(
        "check_mwe",
        skip_routes=True,
        skip_data=True,
        warn_only=True,
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "missing runtime user test_reg_officer" in output
    assert "MWE check completed" in output


def test_check_mwe_accepts_existing_runtime_users_and_open_windows() -> None:
    """The checker should pass when users authenticate and windows are open."""
    for username, group_name in RUNTIME_USERS:
        user = User.objects.create_user(username=username, password=TEST_PASSWORD)
        group, _created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    SemesterStatus._populate_attributes_and_db()
    academic_year = AcademicYear.objects.create(start_date=date(2026, 1, 1))
    Semester.objects.create(
        academic_year=academic_year,
        number=1,
        status_id="registration",
    )
    Semester.objects.create(
        academic_year=academic_year,
        number=2,
        status_id="grade_entry",
    )
    stdout = StringIO()

    call_command(
        "check_mwe",
        skip_routes=True,
        skip_data=True,
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "OK user test_reg_officer" in output
    assert "MWE check completed with 0 error(s) and 0 warning(s)." in output
