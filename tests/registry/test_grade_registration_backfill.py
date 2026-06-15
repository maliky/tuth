"""Tests for grade-backed historical registration reconstruction."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping

import pytest
from django.core.management import call_command

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.registry.grade_registration_reconciliation import student_credit_gaps
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.credit_hours import CreditHour
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db

GRADE_HEADERS = [
    "student_id",
    "academic_year",
    "semester_no",
    "course_dept",
    "course_no",
    "course_title",
    "curriculum",
    "credit_hours",
    "section_no",
    "grade_code",
    "college_code",
]


def _grade_row(**overrides: str) -> dict[str, str]:
    """Return one import-grade row."""
    row = {
        "student_id": "TU-REG-GAP",
        "academic_year": "2025-2026",
        "semester_no": "1",
        "course_dept": "HIST",
        "course_no": "202",
        "course_title": "World History",
        "curriculum": "CURRI_REG_GAP",
        "credit_hours": "3",
        "section_no": "1",
        "grade_code": "B",
        "college_code": "COAS",
    }
    row.update(overrides)
    return row


def _write_grades_tsv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    """Write a small import_grades-compatible TSV."""
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(GRADE_HEADERS) + "\n")
        for row in rows:
            handle.write("\t".join(row.get(header, "") for header in GRADE_HEADERS))
            handle.write("\n")


@pytest.fixture
def imported_grade_without_registration(tmp_path: Path) -> Grade:
    """Create one passing grade without reconstructing its registration."""
    GradeValue.objects.get_or_create(code="B")
    tsv_path = tmp_path / "grades.tsv"
    _write_grades_tsv(tsv_path, [_grade_row()])
    call_command(
        "import_grades",
        file=tsv_path,
        batch_size=1,
        no_reconstruct_registrations=True,
    )
    return Grade.objects.get()


def test_backfill_grade_registrations_dry_run_does_not_mutate(
    imported_grade_without_registration: Grade,
    tmp_path: Path,
) -> None:
    """Dry-run reports the repair without creating registration rows."""
    out = StringIO()

    call_command(
        "backfill_grade_registrations",
        student=imported_grade_without_registration.student.student_id,
        log_path=tmp_path / "dry_run.csv",
        stdout=out,
    )

    assert Registration.objects.count() == 0
    assert "1 would-create" in out.getvalue()


def test_backfill_grade_registrations_apply_repairs_credit_gap(
    imported_grade_without_registration: Grade,
    tmp_path: Path,
) -> None:
    """Apply mode creates a cleared registration and closes the credit gap."""
    student_id = imported_grade_without_registration.student_id
    assert student_credit_gaps(student_id=student_id)

    call_command(
        "backfill_grade_registrations",
        student=imported_grade_without_registration.student.student_id,
        log_path=tmp_path / "apply.csv",
        apply=True,
    )

    registration = Registration.objects.get()
    assert registration.status_id == "cleared"
    assert registration.student_id == imported_grade_without_registration.student_id
    assert registration.section_id == imported_grade_without_registration.section_id
    assert student_credit_gaps(student_id=student_id) == []


def test_backfill_grade_registrations_keeps_existing_same_course_registration(
    imported_grade_without_registration: Grade,
    tmp_path: Path,
) -> None:
    """A same-course registration in another section already covers the grade."""
    RegistrationStatus._populate_attributes_and_db()
    section = imported_grade_without_registration.section
    alternate_section = Section.objects.create(
        semester=section.semester,
        curriculum_course=section.curriculum_course,
        number=99,
    )
    Registration.objects.create(
        student=imported_grade_without_registration.student,
        section=alternate_section,
        status_id="cleared",
    )

    call_command(
        "backfill_grade_registrations",
        student=imported_grade_without_registration.student.student_id,
        log_path=tmp_path / "apply.csv",
        apply=True,
    )

    assert Registration.objects.count() == 1
    assert Registration.objects.get().section == alternate_section


def test_backfill_grade_registrations_repairs_same_course_low_credit_registration(
    imported_grade_without_registration: Grade,
    tmp_path: Path,
) -> None:
    """Same-course coverage must have enough credits to cover the grade."""
    RegistrationStatus._populate_attributes_and_db()
    section = imported_grade_without_registration.section
    low_credit_course = CurriCrs.objects.create(
        curriculum=Curriculum.get_dft("CURRI_LOW_CREDIT"),
        course=section.curriculum_course.course,
        credit_hours=CreditHour.objects.get(code=1),
    )
    low_credit_section = Section.objects.create(
        semester=section.semester,
        curriculum_course=low_credit_course,
        number=98,
    )
    Registration.objects.create(
        student=imported_grade_without_registration.student,
        section=low_credit_section,
        status_id="cleared",
    )

    call_command(
        "backfill_grade_registrations",
        student=imported_grade_without_registration.student.student_id,
        log_path=tmp_path / "apply.csv",
        apply=True,
    )

    assert Registration.objects.count() == 2
    assert Registration.objects.filter(section=section).exists()
    assert (
        student_credit_gaps(student_id=imported_grade_without_registration.student_id)
        == []
    )
