"""Utility helpers used in the finance app."""

from decimal import Decimal


TUITION_RATE_PER_CREDIT = Decimal("5.00")


def tuition_for(course, credit_hours: int) -> Decimal:
    """Calculate the tuition amount for a course.

    Args:
        course: Record kept for context and future rate rules.
        credit_hours: Number of credit hours to bill.

    Returns:
        The total tuition cost.

    Examples:
        With 3 credit hours at the current rate, the result is 15.00.
    """
    return Decimal(credit_hours) * TUITION_RATE_PER_CREDIT
