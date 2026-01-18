"""Utility helpers used in the finance app."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.academics.models.course import CurriculumCourse


TUITION_RATE_PER_CREDIT = Decimal("5.00")


def tuition_for(curriculum_course: "CurriculumCourse") -> Decimal:
    """Calculate the tuition amount for a curriculum course.

    Args:
        curriculum_course: Curriculum course carrying the credit hour value.

    Returns:
        The total tuition cost.

    Examples:
        With 3 credit hours at the current rate, the result is 15.00.
    """
    credit_hours = getattr(curriculum_course, "credit_hours", None)
    credit_code = getattr(credit_hours, "code", None)
    return Decimal(int(credit_code or 0)) * TUITION_RATE_PER_CREDIT
