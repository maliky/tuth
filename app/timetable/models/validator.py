"""Validator module."""

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

from app.academics.constants import MAX_STUDENT_CREDITS

if TYPE_CHECKING:
    from app.timetable.models import Reservation


class CreditLimitValidator:
    """Ensure a student's reservation doesn't exceed the credit limit."""

    def __call__(self, reservation: "Reservation") -> None:
        """Raise ``ValidationError`` if ``reservation`` exceeds max credits."""
        # compute the hours the student would have if this reservation succeeds
        prospective = reservation.credit_hours() + reservation.section.course.credit_hours
        if prospective > MAX_STUDENT_CREDITS:
            raise ValidationError(
                f"Exceeded credit-hour limit ({prospective}/{MAX_STUDENT_CREDITS})."
            )
