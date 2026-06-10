"""Regression tests for historical registration imports."""

from __future__ import annotations

import pytest
from tablib import Dataset

from app.registry.admin.resources_legacy import LegacyRegioResource
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus


@pytest.mark.django_db
def test_legacy_registration_import_accepts_missing_faculty_column() -> None:
    """SmartSchool registration rows do not carry faculty assignments."""
    RegistrationStatus._populate_attributes_and_db()
    dataset = Dataset(
        headers=[
            "student_id",
            "academic_year",
            "semester_no",
            "course_dept",
            "course_no",
            "section_no",
            "credit_hours",
            "course_title",
            "curriculum",
            "college_code",
            "status",
        ]
    )
    dataset.append(
        [
            "36764",
            "2023/2024",
            "1",
            "CHEM",
            "101",
            "2",
            "4.0",
            "Principles of Chemistry",
            "BA - 2ndEd/Eng Lit",
            "EDRCE",
            "registered",
        ]
    )

    result = LegacyRegioResource().import_data(dataset, dry_run=False, raise_errors=True)

    assert not result.has_errors()
    registration = Registration.objects.select_related("section").get()
    assert registration.section.faculty_id is None
