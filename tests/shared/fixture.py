"""Test fixtures of the shared module."""

from __future__ import annotations

from typing import Callable, TypeAlias

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.utils import OperationalError

from app.people.models.student import Student
from app.shared.status.mixins import StatusHistory

StatusHistoryFactory: TypeAlias = Callable[[Student, str], StatusHistory]


def _ensure_table() -> None:
    """Create the status history table if absent."""

    table = StatusHistory._meta.db_table
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
        except OperationalError:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(StatusHistory)


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
def status_history_factory() -> StatusHistoryFactory:
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
