"""Shared GPA helpers for registry consumers."""

from __future__ import annotations

from typing import Iterable, TypedDict, TypeAlias

from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.registry.constants import GPA_EXCLUDED_CODES
from app.registry.models.grade import Grade
from app.timetable.models.semester import Semester


class GpaRowT(TypedDict):
    """Normalized GPA row details used for quality point sums."""

    grade_id: int
    credits: int
    quality_points: float


class GpaResultT(TypedDict):
    """Summary GPA result for a student/semester pair."""

    gpa: float | None
    credits_total: int
    quality_points: float


GpaRowsT: TypeAlias = list[GpaRowT]


def _grade_is_eligible(grade: Grade) -> bool:
    """Return True when a grade should contribute to GPA totals."""
    value = grade.value
    if value is None or value.number is None:
        return False
    grade_code = (value.code or "").lower()
    return grade_code not in GPA_EXCLUDED_CODES


def _grade_credit_hours(grade: Grade) -> int:
    """Return the credit hours for the grade's curriculum course."""
    credit_hours = grade.section.curriculum_course.credit_hours
    return int(getattr(credit_hours, "code", 0) or 0)


def get_grade_points_and_credits(grade: Grade) -> tuple[float, int] | None:
    """Return quality points and credits for GPA calculations.

    Args:
        grade: Grade instance to evaluate.

    Returns:
        Tuple of (quality_points, credits) when eligible, otherwise None.
    """
    if not _grade_is_eligible(grade):
        return None
    _credits = _grade_credit_hours(grade)
    value = grade.value
    if value is None or value.number is None:
        return None
    return float(value.number) * _credits, _credits


def build_gpa_queryset(
    student: Student,
    curriculum: Curriculum,
    semester: Semester | None = None,
) -> QuerySet[Grade]:
    """Return the base queryset for GPA calculations.

    Args:
        student: Student owning the grades.
        curriculum: Curriculum used to scope curriculum courses.
        semester: Optional semester filter.

    Returns:
        QuerySet of Grade rows ready for GPA aggregation.
    """
    qs = Grade.objects.select_related(
        "value",
        "section__semester",
        "section__curriculum_course__credit_hours",
        "section__curriculum_course__course",
    ).filter(
        student=student,
        section__curriculum_course__curriculum=curriculum,
        section__section_registrations__student=student,
    )
    if semester is not None:
        qs = qs.filter(section__semester=semester)
    return qs.distinct()


def _compute_gpa_from_grades(grades: Iterable[Grade]) -> GpaResultT:
    """Aggregate quality points and credits into a GPA summary."""
    quality_points = 0.0
    credits_total = 0
    for grade in grades:
        result = get_grade_points_and_credits(grade)
        if result is None:
            continue
        points, _credits = result
        quality_points += points
        credits_total += _credits
    gpa = quality_points / credits_total if credits_total else None
    return {
        "gpa": gpa,
        "credits_total": credits_total,
        "quality_points": quality_points,
    }


def get_gpa(semester: Semester, student: Student, curriculum: Curriculum) -> GpaResultT:
    """Return GPA data for a student in a single semester/curriculum.

    Args:
        semester: Target semester.
        student: Student to evaluate.
        curriculum: Curriculum used for credit hour lookup.

    Returns:
        GPA summary for the semester.
    """
    grades = build_gpa_queryset(student=student, curriculum=curriculum, semester=semester)
    return _compute_gpa_from_grades(grades)


def get_cumulative_gpa(student: Student, curriculum: Curriculum) -> GpaResultT:
    """Return cumulative GPA data across all semesters in a curriculum."""
    grades = build_gpa_queryset(student=student, curriculum=curriculum, semester=None)
    return _compute_gpa_from_grades(grades)
