"""Shared grade portal helpers for faculty and registrar workflows."""

from __future__ import annotations

from typing import TypeAlias

from app.registry.models.grade import Grade, GradeValue

GradePortalErrorTypeT: TypeAlias = type["GradePortalError"]


class GradePortalError(ValueError):
    """Raised when a portal grade mutation cannot be applied."""


def grade_value_options() -> list[GradeValue]:
    """Return canonical grade values for grade select widgets."""
    GradeValue._populate_attributes_and_db()
    return list(GradeValue.objects.order_by("-number", "code"))


def grade_value_for_code(
    grade_code: str,
    *,
    error_type: GradePortalErrorTypeT = GradePortalError,
) -> GradeValue | None:
    """Return a grade value for a submitted code, or None for a blank grade."""
    clean_code = grade_code.strip().lower()
    if not clean_code:
        return None
    GradeValue._populate_attributes_and_db()
    value = GradeValue.objects.filter(code=clean_code).first()
    if value is None:
        raise error_type(f"Unknown grade code: {grade_code}.")
    return value


def set_grade_code(
    grade: Grade,
    grade_code: str,
    *,
    error_type: GradePortalErrorTypeT = GradePortalError,
) -> bool:
    """Set one grade code and return whether the row changed."""
    value = grade_value_for_code(grade_code, error_type=error_type)
    next_value_id = value.id if value else None
    if grade.value_id == next_value_id:
        return False
    grade.value = value
    grade.save(update_fields=["value"])
    return True


__all__ = [
    "GradePortalError",
    "GradePortalErrorTypeT",
    "grade_value_for_code",
    "grade_value_options",
    "set_grade_code",
]
