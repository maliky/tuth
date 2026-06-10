"""Tests for non-destructive TUCurricula/current-data reconciliation."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from app.academics.models import College, Course, CurriCrs, Curriculum, Department
from app.people.models import Student
from app.registry.models import Grade, GradeValue, Registration
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db


def _write_tsv(path: Path, headers: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    """Write a tiny import TSV fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a TSV report file."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_import_dir(import_dir: Path) -> None:
    """Create minimal org-derived import files for reconciliation."""
    _write_tsv(
        import_dir / "academic_course.tsv",
        (
            "college_code",
            "course_college_code",
            "course_dept",
            "course_no",
            "course_title",
            "credit_hours",
            "description",
            "source_course_key",
            "source_files",
        ),
        [
            {
                "college_code": "COAS",
                "course_college_code": "COAS",
                "course_dept": "MATH",
                "course_no": "101",
                "course_title": "College Algebra",
                "credit_hours": "4",
                "description": "Org description",
                "source_course_key": "MATH101",
                "source_files": "test.org",
            },
            {
                "college_code": "COAS",
                "course_college_code": "COAS",
                "course_dept": "PHYS",
                "course_no": "101",
                "course_title": "Physics I",
                "credit_hours": "4",
                "description": "Mechanics",
                "source_course_key": "PHYS101",
                "source_files": "test.org",
            },
        ],
    )
    _write_tsv(
        import_dir / "academic_curriculum.tsv",
        (
            "college_code",
            "curriculum_college_code",
            "curriculum",
            "long_name",
            "status",
            "source_college",
            "source_slug",
        ),
        [
            {
                "college_code": "COAS",
                "curriculum_college_code": "COAS",
                "curriculum": "CAS-MATH",
                "long_name": "Bachelor of Science in Mathematics",
                "status": "pending",
                "source_college": "cas",
                "source_slug": "math",
            }
        ],
    )
    _write_tsv(
        import_dir / "academic_curriculum_course.tsv",
        (
            "college_code",
            "curriculum_college_code",
            "course_college_code",
            "curriculum",
            "course_dept",
            "course_no",
            "course_title",
            "credit_hours",
            "year_number",
            "semester_number",
            "level_number",
            "required_group_number",
            "min_validated_credits",
            "is_required",
            "source_course_key",
            "source_program",
        ),
        [
            {
                "college_code": "COAS",
                "curriculum_college_code": "COAS",
                "course_college_code": "COAS",
                "curriculum": "CAS-MATH",
                "course_dept": "MATH",
                "course_no": "101",
                "course_title": "College Algebra",
                "credit_hours": "4",
                "year_number": "1",
                "semester_number": "1",
                "level_number": "1",
                "required_group_number": "0",
                "min_validated_credits": "0",
                "is_required": "true",
                "source_course_key": "MATH101",
                "source_program": "Bachelor of Science in Mathematics",
            }
        ],
    )


def _create_current_referenced_catalog() -> None:
    """Create current data that references one mismatched curriculum course."""
    college = College.objects.create(code="COAS", long_name="Arts and Sciences")
    department = Department.objects.create(code="MATH", college=college)
    course = Course.objects.create(
        department=department,
        number="101",
        title="Old Algebra",
        description="Old description",
    )
    curriculum = Curriculum.objects.create(
        short_name="CAS-MATH",
        college=college,
        long_name="Old Mathematics Program",
    )
    curriculum_course = CurriCrs.objects.create(
        curriculum=curriculum,
        course=course,
        credit_hours_id=3,
        level_number=1,
    )
    academic_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    semester = Semester.objects.create(academic_year=academic_year, number=1)
    section = Section.objects.create(
        semester=semester,
        curriculum_course=curriculum_course,
        number=1,
    )
    user = User.objects.create_user(
        username="reconcile_student",
        first_name="Ada",
        last_name="Course",
    )
    student = Student(user=user, last_enrolled_semester=semester)
    student.primary_curriculum = curriculum
    student.save()
    Registration.objects.create(student=student, section=section)
    Grade.objects.create(student=student, section=section, value=GradeValue.get_dft())


def test_reconcile_tucurricula_snapshots_and_flags_referenced_rows(tmp_path) -> None:
    """Command should preserve student history while reporting org differences."""
    import_dir = tmp_path / "import"
    output_dir = tmp_path / "reports"
    _write_import_dir(import_dir)
    _create_current_referenced_catalog()

    call_command(
        "reconcile_tucurricula",
        import_dir=str(import_dir),
        output_dir=str(output_dir),
    )

    grade_rows = _read_tsv(output_dir / "current_grades.tsv")
    course_rows = _read_tsv(output_dir / "course_reconciliation.tsv")
    curriculum_course_rows = _read_tsv(
        output_dir / "curriculum_course_reconciliation.tsv"
    )
    mapping_rows = _read_tsv(output_dir / "curriculum_mapping_candidates.tsv")
    math_course = next(row for row in course_rows if row["course_key"] == "MATH101")
    phys_course = next(row for row in course_rows if row["course_key"] == "PHYS101")
    math_program = next(
        row
        for row in curriculum_course_rows
        if row["curriculum_course_key"] == "CASMATH|MATH101"
    )

    assert grade_rows[0]["course_key"] == "MATH101"
    assert grade_rows[0]["student_id"]
    assert math_course["action"] == "update_course_metadata"
    assert math_course["usage_total"] == "3"
    assert phys_course["action"] == "create_course"
    assert math_program["action"] == "review_referenced_curriculum_course"
    assert "credit_hours" in math_program["notes"]
    assert mapping_rows[0]["current_curriculum"] == "CAS-MATH"
    assert mapping_rows[0]["org_curriculum"] == "CAS-MATH"
    assert "mutation: none" in (output_dir / "SUMMARY.txt").read_text(encoding="utf-8")
