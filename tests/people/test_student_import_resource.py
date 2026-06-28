"""Tests for student import resource normalization."""

from __future__ import annotations

from datetime import date

import pytest
from tablib import Dataset

from app.academics.choices import AcademicCareer
from app.people.admin.resources import StdResource
from app.people.models.student import Student


def test_student_resource_birth_date_accepts_iso_date() -> None:
    """Student import should accept SmartSchool ISO date-only values."""
    widget = StdResource().fields["birth_date"].widget

    assert widget.clean("1900-01-01") == date(1900, 1, 1)
    assert widget.clean("") is None


@pytest.mark.django_db
def test_student_resource_defaults_legacy_academic_career(curri_factory) -> None:
    """Older student TSVs can omit academic_career."""
    curri_factory("BACC")
    dataset = Dataset(
        headers=[
            "username",
            "student_id",
            "long_name",
            "curriculum_shortname",
        ]
    )
    dataset.append(["legacy.student", "TU-0001", "Legacy Student", "BACC"])

    result = StdResource().import_data(dataset, dry_run=False, raise_errors=True)

    assert not result.has_errors()
    student = Student.objects.get(user__username="legacy.student")
    assert student.academic_career == AcademicCareer.UNDERGRADUATE
