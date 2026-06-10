"""Shared GPA helpers for registry consumers."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping, TypedDict, TypeAlias

from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.registry.constants import GPA_EXCLUDED_CODES
from app.registry.models.grade import Grade
from app.shared.course_wrangling import course_key
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
CourseAliasMapT: TypeAlias = Mapping[str, str]

TRANSCRIPT_COURSE_ALIASES: CourseAliasMapT = {
    "HIST101": "HIST201",
    "HIST102": "HIST202",
}


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


def canonical_grade_course_key(grade: Grade) -> str:
    """Return the transcript-equivalent course key for a grade row."""
    course = grade.section.curriculum_course.course
    key = course_key(course.department.code, course.number)
    return TRANSCRIPT_COURSE_ALIASES.get(key, key)


def effective_transcript_grades(grades: Iterable[Grade]) -> list[Grade]:
    """Return effective transcript grades with approved duplicate aliases collapsed."""
    selected: dict[str, Grade] = {}
    order: list[str] = []
    for grade in grades:
        if not grade.is_effective:
            continue
        key = canonical_grade_course_key(grade)
        if not key:
            continue
        current = selected.get(key)
        if current is None:
            selected[key] = grade
            order.append(key)
            continue
        if _grade_is_newer(grade, current):
            selected[key] = grade
    return [selected[key] for key in order]


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
        "section__curriculum_course__course__department",
    ).filter(
        student=student,
        section__curriculum_course__curriculum=curriculum,
        is_effective=True,
    )
    if semester is not None:
        qs = qs.filter(section__semester=semester)
    return qs.distinct()


def _compute_gpa_from_grades(grades: Iterable[Grade]) -> GpaResultT:
    """Aggregate quality points and credits into a GPA summary."""
    quality_points = 0.0
    credits_total = 0
    for grade in effective_transcript_grades(grades):
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


def _grade_is_newer(candidate: Grade, current: Grade) -> bool:
    """Return True when candidate is the preferred transcript attempt."""
    return _grade_sort_key(candidate) > _grade_sort_key(current)


def _grade_sort_key(grade: Grade) -> tuple[date, int, date, int]:
    """Return a stable recency key for transcript duplicate collapse."""
    semester = grade.section.semester
    semester_date = semester.start_date or semester.academic_year.start_date or date.min
    graded_on = grade.graded_on or date.min
    return (semester_date, semester.number, graded_on, grade.id or 0)
