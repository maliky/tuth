"""Test fixtures of the shared module."""

from __future__ import annotations

from typing import Callable, TypeAlias

import pytest
from django.apps import apps
from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth.management import create_permissions
from django.contrib.contenttypes.models import ContentType
from django.db import connection, models
from django.db.utils import OperationalError, ProgrammingError

from app.people.models.student import Student
from app.shared.status.mixins import StatusHistory

StatusHistoryFactoryT: TypeAlias = Callable[[Student, str], StatusHistory]
ModelTypeT: TypeAlias = type[models.Model]


def _ensure_model_table(model: ModelTypeT) -> None:
    """Create the model table if it does not yet exist."""
    table = model._meta.db_table
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT 1 FROM {connection.ops.quote_name(table)} LIMIT 1")
        except (OperationalError, ProgrammingError):
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(model)


def _ensure_auth_tables() -> None:
    """Ensure auth/contenttypes tables exist for tests without migrations."""
    # Tests can run without migrations; build auth/contenttypes tables to avoid
    # missing auth_user/permission errors when model factories touch auth models.
    # Order matters for FK constraints and M2M table creation.
    _ensure_model_table(ContentType)
    _ensure_model_table(Permission)
    _ensure_model_table(Group)
    _ensure_model_table(Group.permissions.through)
    _ensure_model_table(User)
    _ensure_model_table(User.groups.through)
    _ensure_model_table(User.user_permissions.through)
    # Ensure content types and permissions exist when migrations are skipped.
    for app_config in apps.get_app_configs():
        create_permissions(app_config, verbosity=0)


def _ensure_table() -> None:
    """Create the status history table if absent."""
    _ensure_model_table(StatusHistory)


@pytest.fixture(scope="session", autouse=True)
def _auth_tables(django_db_setup, django_db_blocker) -> None:
    """Ensure auth/contenttypes tables exist for all tests."""
    with django_db_blocker.unblock():
        _ensure_auth_tables()


@pytest.fixture(scope="session", autouse=True)
def _status_history_table(django_db_setup, django_db_blocker) -> None:
    """Ensure the StatusHistory table exists for all tests."""
    with django_db_blocker.unblock():
        _ensure_table()


@pytest.fixture
def status_history(student: Student) -> StatusHistory:
    """Default status history attached to a student."""
    _ensure_table()
    ct = ContentType.objects.get_for_model(student)
    return StatusHistory.objects.create(
        status="pending",
        content_type=ct,
        object_id=student.id,
    )


@pytest.fixture
def status_history_factory() -> StatusHistoryFactoryT:
    """Return a callable to build status history entries."""

    def _make(student: Student, status: str = "pending") -> StatusHistory:
        _ensure_table()
        ct = ContentType.objects.get_for_model(student)
        return StatusHistory.objects.create(
            status=status,
            content_type=ct,
            object_id=student.id,
        )

    return _make
