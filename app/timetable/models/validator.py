from django.core.exceptions import ValidationError

from app.shared.constants import MAX_STUDENT_CREDITS


class CreditLimitValidator:
    """Ensure a student's reservation doesn't exceed the credit limit."""

    def __call__(self, reservation):
        # compute the hours the student would have if this reservation succeeds
        prospective = reservation.credit_hours() + reservation.section.course.credit_hours
        if prospective > MAX_STUDENT_CREDITS:
            raise ValidationError(
                f"Exceeded credit-hour limit ({prospective}/{MAX_STUDENT_CREDITS})."
            )
