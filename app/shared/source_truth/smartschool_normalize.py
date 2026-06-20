"""Shared SmartSchool normalization helpers."""

from __future__ import annotations

from app.shared.course_wrangling import (
    CourseIdentityResultT,
    parse_course_identity_result,
)
from app.shared.student_ids import canonical_student_id
from app.shared.source_truth.io import RowT
from app.timetable.utils import normalize_sem_code


def first_value(row: RowT, *keys: str) -> str:
    """Return the first non-empty value from row by candidate column name."""
    for key in keys:
        value = row.get(key, "")
        if value:
            return value.strip()
    return ""


def name_from_parts(first: str, middle: str, last: str) -> str:
    """Join name parts while dropping blanks."""
    return " ".join(part for part in (first, middle, last) if part).strip()


def legacy_curriculum_from_row(row: RowT) -> str:
    """Return the best SmartSchool legacy curriculum label from a row."""
    return (
        first_value(row, "Major")
        or first_value(row, "Curriculum")
        or first_value(row, "ProgramID", "EnrollmentType")
    )


def clean_student_id(value: str) -> str:
    """Return a canonical import id for TU-prefixed student identifiers."""
    return canonical_student_id(value)


def course_identity_from_row(row: RowT) -> CourseIdentityResultT | None:
    """Return a normalized SmartSchool course identity when it is parseable."""
    return parse_course_identity_result(
        first_value(row, "CourseCode"),
        first_value(row, "CourseNo"),
    )


def semester_no(value: str) -> str:
    """Normalize SmartSchool semester labels to numeric text."""
    token = value.strip().upper()
    if token in {"SUMMER", "VAC", "VACATION"}:
        return "3"
    return int_text(token, default="1")


def semester_code(academic_year: str, semester: str) -> str:
    """Return a SemCodeWgt-compatible semester code."""
    return normalize_sem_code("", year_value=academic_year, sem_value=semester)


def date_value(value: str) -> str:
    """Convert SmartSchool ISO datetime strings to date/datetime-widget text."""
    if "T" not in value:
        return value
    return value.split("T", maxsplit=1)[0]


def int_text(value: str, *, default: str = "0") -> str:
    """Return integer-looking text for numeric SmartSchool fields."""
    try:
        return str(int(float(value.strip())))
    except ValueError:
        return default


__all__ = [
    "clean_student_id",
    "course_identity_from_row",
    "date_value",
    "first_value",
    "int_text",
    "legacy_curriculum_from_row",
    "name_from_parts",
    "semester_code",
    "semester_no",
]
