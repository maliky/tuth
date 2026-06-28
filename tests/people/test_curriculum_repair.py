"""Tests for oversized primary-curriculum repair."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import CurriStatus, Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import (
    StdCurriEnroll,
    set_primary_std_curri_enroll,
)
from app.registry.models.credit_hours import CreditHour
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester

pytestmark = pytest.mark.django_db


def _defaults() -> None:
    """Create lookup rows required by the repair fixtures."""
    CurriStatus._populate_attributes_and_db()
    RegistrationStatus._populate_attributes_and_db()
    GradeValue._populate_attributes_and_db()


def _semester() -> Semester:
    """Return one deterministic semester for evidence rows."""
    academic_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    return Semester.objects.create(academic_year=academic_year, number=1)


def _curriculum(
    college: College,
    short_name: str,
    *,
    approved: bool,
    active: bool,
) -> Curriculum:
    """Create a curriculum with the requested validation state."""
    return Curriculum.objects.create(
        college=college,
        short_name=short_name,
        long_name=f"{short_name} Program",
        status_id="approved" if approved else "pending",
        is_active=active,
    )


def _course_row(
    curriculum: Curriculum,
    department: Department,
    number: str,
    credits: int,
) -> CurriCrs:
    """Create one course and curriculum-course row."""
    credit_hours, _created = CreditHour.objects.get_or_create(
        code=credits,
        defaults={"label": str(credits)},
    )
    course = Course.objects.create(
        department=department,
        number=number,
        title=f"Repair Course {number}",
    )
    return CurriCrs.objects.create(
        curriculum=curriculum,
        course=course,
        credit_hours=credit_hours,
    )


def _student(username: str, source: Curriculum, semester: Semester) -> Student:
    """Create a student with one oversized primary enrollment."""
    user = User.objects.create_user(username=username)
    student = Student(user=user, last_enrolled_semester=semester)
    student.student_id = f"SID-{username.upper()}"
    student.save()
    set_primary_std_curri_enroll(student, source, entry_semester_id=semester.id)
    return student


def _evidence(student: Student, curriculum_course: CurriCrs, semester: Semester) -> None:
    """Create registration and grade evidence for one curriculum course."""
    section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=semester,
        number=1,
    )
    Registration.objects.create(student=student, section=section)
    Grade.objects.create(
        student=student,
        section=section,
        value=GradeValue.objects.get(code="b"),
    )


def _audit_rows(path: Path) -> list[dict[str, str]]:
    """Read repair audit rows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _repair_fixture() -> tuple[Student, Curriculum, Curriculum, Semester, CurriCrs]:
    """Create a deterministic oversized-to-approved repair fixture."""
    _defaults()
    semester = _semester()
    college = College.objects.create(code="CRFIX", long_name="Curriculum Repair")
    department = Department.objects.create(code="CRF", college=college)
    source = _curriculum(college, "BIO-OVERSIZED", approved=False, active=False)
    for index in range(3):
        _course_row(source, department, f"80{index}", 80)
    target = _curriculum(college, "BIO-TARGET", approved=True, active=True)
    target_course = _course_row(target, department, "101", 3)
    _course_row(target, department, "102", 3)
    other = _curriculum(college, "OTHER", approved=True, active=True)
    _course_row(other, department, "201", 3)
    student = _student("repair_student", source, semester)
    _evidence(student, target_course, semester)
    return student, source, target, semester, target_course


def test_repair_oversized_curriculum_dry_run_does_not_mutate(tmp_path) -> None:
    """Dry-run should report deterministic moves without changing enrollment."""
    student, source, target, _semester_obj, _target_course = _repair_fixture()
    audit_path = tmp_path / "repair_dry.csv"
    output = StringIO()

    call_command(
        "repair_oversized_curriculum_enrollments",
        "--log-path",
        str(audit_path),
        stdout=output,
    )

    assert Student.objects.get(pk=student.pk).primary_curriculum == source
    rows = _audit_rows(audit_path)
    assert rows[0]["action"] == "would_move"
    assert rows[0]["target_curriculum_id"] == str(target.id)
    assert "1 would-move" in output.getvalue()


def test_repair_oversized_curriculum_apply_moves_primary(tmp_path) -> None:
    """Apply mode should move deterministic oversized primary enrollments."""
    student, source, target, semester, _target_course = _repair_fixture()
    audit_path = tmp_path / "repair_apply.csv"

    call_command(
        "repair_oversized_curriculum_enrollments",
        "--apply",
        "--log-path",
        str(audit_path),
        stdout=StringIO(),
    )

    assert Student.objects.get(pk=student.pk).primary_curriculum == target
    target_enrollment = StdCurriEnroll.objects.get(student=student, curriculum=target)
    source_enrollment = StdCurriEnroll.objects.get(student=student, curriculum=source)
    assert target_enrollment.is_primary is True
    assert target_enrollment.entry_semester == semester
    assert source_enrollment.is_primary is False
    assert source_enrollment.is_active is False
    rows = _audit_rows(audit_path)
    assert rows[0]["action"] == "moved"
    assert rows[0]["reason"] == "approved_active_majority_evidence_match"


def test_repair_oversized_curriculum_keeps_ambiguous_rows_unresolved(tmp_path) -> None:
    """A tie between approved active candidates should not mutate data."""
    _defaults()
    semester = _semester()
    college = College.objects.create(code="CRTIE", long_name="Curriculum Tie")
    department = Department.objects.create(code="CRT", college=college)
    source = _curriculum(college, "TIE-SOURCE", approved=False, active=False)
    for index in range(3):
        _course_row(source, department, f"90{index}", 80)
    candidate_a = _curriculum(college, "TIE-A", approved=True, active=True)
    candidate_b = _curriculum(college, "TIE-B", approved=True, active=True)
    course_a = _course_row(candidate_a, department, "301", 3)
    course_b = _course_row(candidate_b, department, "302", 3)
    student = _student("repair_tie", source, semester)
    _evidence(student, course_a, semester)
    _evidence(student, course_b, semester)
    audit_path = tmp_path / "repair_tie.csv"

    call_command(
        "repair_oversized_curriculum_enrollments",
        "--apply",
        "--log-path",
        str(audit_path),
        stdout=StringIO(),
    )

    assert Student.objects.get(pk=student.pk).primary_curriculum == source
    rows = _audit_rows(audit_path)
    assert rows[0]["action"] == "unresolved"
    assert rows[0]["reason"] == "ambiguous_top_match"


def test_repair_oversized_curriculum_rejects_unrelated_program_family(
    tmp_path,
) -> None:
    """Majority evidence alone should not move across unrelated program names."""
    _defaults()
    semester = _semester()
    college = College.objects.create(code="CRFAM", long_name="Curriculum Family")
    department = Department.objects.create(code="CRY", college=college)
    source = _curriculum(college, "ENV-SOURCE", approved=False, active=False)
    for index in range(3):
        _course_row(source, department, f"70{index}", 80)
    candidate = _curriculum(college, "FREN", approved=True, active=True)
    course = _course_row(candidate, department, "401", 3)
    student = _student("repair_family", source, semester)
    _evidence(student, course, semester)
    audit_path = tmp_path / "repair_family.csv"

    call_command(
        "repair_oversized_curriculum_enrollments",
        "--apply",
        "--log-path",
        str(audit_path),
        stdout=StringIO(),
    )

    assert Student.objects.get(pk=student.pk).primary_curriculum == source
    rows = _audit_rows(audit_path)
    assert rows[0]["action"] == "unresolved"
    assert rows[0]["reason"] == "no_same_college_program_family_match"
