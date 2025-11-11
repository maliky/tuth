"""Payment module."""
from __future__ import annotations

from django.db import models

from simple_history.models import HistoricalRecords


class Invoice(models.Model):
    """Invoice for a curriculum_course.

    Attributes:
        curriculum_course (academics.CurriculumCourse): Course in a curriculum
            being paid for.
        amount_due (Decimal): Value of the transaction.
        method (str): Payment method from :class:PaymentMethod.
        recorded_by (people.Staff): Staff member who logged the payment.
        created_at (datetime): Timestamp when the record was created.

    A student can pay twice for the same curriculum_course if they fail and need
    to retake it, but the semester will differ.
    Example:
        >>> Payment.objects.create(
        ...     curriculum_course=curriculum_course,
        ...     amount_due=Decimal("10.00"),

        ... )
    """
    # ~~~~~~~~ Mandatory ~~~~~~~~
    curriculum_course = models.OneToOneField(
        "academics.CurriculumCourse", on_delete=models.CASCADE
    )
    student = models.ForeignKey("people.Student", on_delete=models.PROTECT)
    semester = models.ForeignKey("timetable.Semester", on_delete=models.PROTECT)
    amount_due = models.DecimalField(max_digits=8, decimal_places=2)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()
    created_at = models.DateTimeField(auto_now_add=True)

    # ~~~~~~~~ Optional ~~~~~~~~
    recorded_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
    )
    scholarship = models.ForeignKey(
        "finance.scholarship", on_delete=models.PROTECT, null=True
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return a concise representation of the payment."""
        return f"{self.curriculum_course} - {self.amount_due}"
