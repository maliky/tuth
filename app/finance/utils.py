from decimal import Decimal

from app.shared.constants import TUITION_RATE_PER_CREDIT


def tuition_for(course, credit_hours: int) -> Decimal:
    """Return tuition amount for a course."""
    return Decimal(credit_hours) * TUITION_RATE_PER_CREDIT
