"""Tests for the import_grades management command."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pytest
from django.core.management import call_command

from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator

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
    """Return a base grade row with optional overrides."""
    base = {
        "student_id": "TU-0001",
        "academic_year": "2025-2026",
        "semester_no": "1",
        "course_dept": "MATH",
        "course_no": "101.0",
        "course_title": "Intro to Math",
        "curriculum": "CURRI_TEST",
        "credit_hours": "3",
        "section_no": "1",
        "grade_code": "A",
        "college_code": "COAS",
    }
    base.update(overrides)
    return base


def _write_grades_tsv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    """Write a TSV file matching the import_grades expected columns."""
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(GRADE_HEADERS) + "\n")
        for row in rows:
            values = [row.get(header, "") for header in GRADE_HEADERS]
            handle.write("\t".join(values) + "\n")


@pytest.fixture
def grade_values() -> None:
    """Seed GradeValue entries needed by the import command."""
    GradeValue.objects.get_or_create(code="A")
    GradeValue.objects.get_or_create(code="B")


@pytest.mark.parametrize(
    "rows, expected_grades, expects_default_student",
    [
        ([_grade_row()], 1, False),
        ([(_grade_row()), (_grade_row())], 1, False),
        ([_grade_row(grade_code="Z")], 0, False),
        ([_grade_row(student_id="")], 1, True),
    ],
    ids=["valid", "duplicate_rows", "unknown_grade", "missing_student_id"],
)
def test_import_grades_command_rows(
    tmp_path, grade_values, rows, expected_grades, expects_default_student
):
    """Import grades from TSV rows and validate edge-case handling."""
    tsv_path = tmp_path / "grades.tsv"
    _write_grades_tsv(tsv_path, rows)

    call_command("import_grades", file=tsv_path, batch_size=1)

    assert Grade.objects.count() == expected_grades
    if expects_default_student and expected_grades:
        default_student = Student.get_dft()
        created_grade = Grade.objects.first()
        assert created_grade is not None
        assert created_grade.student_id == default_student.id


def test_import_grades_dry_run_rolls_back(tmp_path, grade_values) -> None:
    """Dry-run should validate rows without writing Grade records."""
    tsv_path = tmp_path / "grades.tsv"
    _write_grades_tsv(tsv_path, [_grade_row()])

    call_command("import_grades", file=tsv_path, batch_size=1, dry_run=True)

    assert Grade.objects.count() == 0
