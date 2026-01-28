"""Course fee module."""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import FeeType


class CourseFee(models.Model):
    """Additional fee charged for a course.

    Attributes:
        course: Course fee applies to.
        semester: Optional semester override (null = default).
        fee_type: Fee type label for the fee.
        amount: Monetary value of the fee.

    Example:
        >>> from decimal import Decimal
        >>> CourseFee.objects.create(
        ...     course=course,
        ...     fee_type=FeeType.objects.get(code='lab'),
        ...     semester=semester,
        ...     amount=Decimal("25.00"),
        ... )
    """

    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.CASCADE,
        related_name="course_fees",
    )
    semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="course_fees",
    )
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.CASCADE,
        related_name="course_fees",
        default="other",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        """Ensure fee_type exists before saving."""
        FeeType.objects.get_or_create(code=self.fee_type_id)
        return super().save(*args, **kwargs)

    @classmethod
    def resolve_amount(cls, course, semester) -> Decimal:
        """Return the best matching fee amount for the given course/semester."""
        if semester:
            fee = cls.objects.filter(course=course, semester=semester).first()
            if fee:
                return fee.amount
        fee = cls.objects.filter(course=course, semester__isnull=True).first()
        if fee:
            return fee.amount
        return Decimal("0.00")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "fee_type"],
                name="uniq_course_fee_type_per_semester",
            ),
            models.UniqueConstraint(
                fields=["course","fee_type"],
                condition=Q(semester__isnull=True),
                name="uniq_course_fee_type_default",
            ),
        ]
        ordering = ["course", "semester"]


class CurriculumCourseFee(models.Model):
    """Additional fee charged for a specific CurriculumCourse.

    This overrides CourseFee when set.
    """

    curriculum_course = models.ForeignKey(
        "academics.CurriculumCourse",
        on_delete=models.CASCADE,
        related_name="curriculum_fees",
    )
    semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="curriculum_course_fees",
    )
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.CASCADE,
        related_name="curriculum_course_fees",
        default="other",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    history = HistoricalRecords()

    @classmethod
    def resolve_amount(cls, curriculum_course, semester) -> Decimal:
        """Return the best matching fee amount for a curriculum course."""
        if semester:
            fee = cls.objects.filter(
                curriculum_course=curriculum_course, semester=semester
            ).first()
            if fee:
                return fee.amount
        fee = cls.objects.filter(
            curriculum_course=curriculum_course, semester__isnull=True
        ).first()
        if fee:
            return fee.amount
        return CourseFee.resolve_amount(curriculum_course.course, semester)

    @classmethod
    def total_fee(cls, curriculum_course, semester) -> Decimal:
        """Return tuition plus resolved additional fees for a curriculum course."""
        return curriculum_course.total_fee(semester)

    def save(self, *args, **kwargs):
        """Ensure a default fee exists when saving a semester-specific fee."""
        FeeType.objects.get_or_create(code=self.fee_type_id)
        super().save(*args, **kwargs)
        if not self.semester_id:
            return
        cls = type(self)
        if not cls.objects.filter(
            curriculum_course=self.curriculum_course,
            semester__isnull=True,
            fee_type=self.fee_type,
        ).exists():
            cls.objects.get_or_create(
                curriculum_course=self.curriculum_course,
                semester=None,
                fee_type=self.fee_type,
                defaults={"amount": self.amount, "fee_type": self.fee_type},
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum_course", "semester","fee_type"],
                name="uniq_curriculum_course_fee_type_per_semester",
            ),
            models.UniqueConstraint(
                fields=["curriculum_course", "fee_type"],
                condition=Q(semester__isnull=True),
                name="uniq_curriculum_course_fee_type_default",
            ),
        ]
        ordering = ["curriculum_course", "semester"]
