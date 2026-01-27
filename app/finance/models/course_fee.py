"""Course fee module."""

from __future__ import annotations

from django.db import models
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import FeeType


class CourseFee(models.Model):
    """Additional fee charged for a course.

    Attributes:
        course : Course fee applies to.
        fee_type (str): Type of fee as defined in :class:FeeType.
        amount (Decimal): Monetary value of the fee.

    Example:
        >>> from decimal import Decimal
        >>> CourseFee.objects.create(
        ...     course=course,
        ...     fee_type=FeeType.objects.get(code='lab'),
        ...     amount=Decimal("25.00"),
        ... )
        >>> CourseFee.objects.create(section=course, fee_type=FeeType.LAB, amount=50)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    course = models.ForeignKey("academic.Course", on_delete=models.CASCADE)
    semester = models.ForeignKey("timetable.Semester", on_delete=models.CASCADE)
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.CASCADE,
        related_name="sections_fees",
        default="other",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        """Ensure the status exist befor saving."""
        FeeType.objects.get_or_create(code=self.fee_type_id)
        return super().save(*args, **kwargs)

class CurriculumCourseFee(CourseFee, models.Model):
    """Additional fee charged for a specific CurriculumCourse.

    For the same course Fee may different if not offered in the same curriculum.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    curriculum_course = models.ForeignKey("academic.CurriculumCourse", on_delete=models.CASCADE)
