"""Tests for shared admin helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

import pytest

from app.shared.admin import core as shared_admin_core
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus

pytestmark = pytest.mark.django_db


def _freeze_now(monkeypatch: pytest.MonkeyPatch, target_date: date) -> None:
    """Force timezone.now() to return a stable datetime for tests."""
    # Monkeypatch keeps the override scoped to the test without touching settings.
    frozen = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        12,
        0,
        0,
        tzinfo=dt_timezone.utc,
    )
    monkeypatch.setattr(shared_admin_core.timezone, "now", lambda: frozen)


# > Test 0 revoir
def test_get_current_sem_uses_latest_started(monkeypatch: pytest.MonkeyPatch):
    """Select the closest semester whose start date is not in the future."""
    SemesterStatus._populate_attributes_and_db()
    today = date(2025, 10, 10)
    _freeze_now(monkeypatch, today)
    academic_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    Semester.objects.create(
        academic_year=academic_year,
        number=1,
        start_date=date(2025, 8, 15),
    )
    current = Semester.objects.create(
        academic_year=academic_year,
        number=2,
        start_date=date(2025, 10, 1),
    )
    Semester.objects.create(
        academic_year=academic_year,
        number=3,
        start_date=date(2025, 12, 1),
    )

    assert Semester.get_current_sem() == current
