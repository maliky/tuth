"""Tests for the bulk user password reset command."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_reset_user_passwords_preserves_excluded_user() -> None:
    """Command should reset target users and leave excluded accounts unchanged."""
    User = get_user_model()
    dev = User.objects.create_user("dev", password="dev-secret")
    first = User.objects.create_user("first", password="old-first")
    second = User.objects.create_user("second", password="old-second")
    dev_hash = dev.password
    stdout = StringIO()

    call_command(
        "reset_user_passwords",
        password="PassW0rd!",
        exclude=["dev"],
        stdout=stdout,
    )

    dev.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()
    assert dev.password == dev_hash
    assert dev.check_password("dev-secret")
    assert first.check_password("PassW0rd!")
    assert second.check_password("PassW0rd!")


def test_reset_user_passwords_dry_run_does_not_write() -> None:
    """Dry-run should report the target count without changing password hashes."""
    User = get_user_model()
    dev = User.objects.create_user("dev", password="dev-secret")
    target = User.objects.create_user("target", password="old-target")
    dev_hash = dev.password
    target_hash = target.password
    stdout = StringIO()

    call_command(
        "reset_user_passwords",
        password="PassW0rd!",
        exclude=["dev"],
        dry_run=True,
        stdout=stdout,
    )

    dev.refresh_from_db()
    target.refresh_from_db()
    assert dev.password == dev_hash
    assert target.password == target_hash
