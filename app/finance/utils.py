"""Utility helpers used in the finance app."""

from decimal import Decimal

from app.shared.constants.finance import TUITION_RATE_PER_CREDIT


def tuition_for(course, credit_hours: int) -> Decimal:
    """Calculate the tuition amount for a course.

    Parameters
    ----------
    course
        The course instance for which tuition is calculated.
    credit_hours : int
        Number of credit hours to bill.

    Returns
    -------
    Decimal
        The total tuition cost.
    """
    return Decimal(credit_hours) * TUITION_RATE_PER_CREDIT
