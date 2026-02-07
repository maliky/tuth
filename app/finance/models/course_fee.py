"""Course fee module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, TypeAlias

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import FeeType

if TYPE_CHECKING:
    from app.academics.models.course import Course
    from app.academics.models.curriculum_course import CurriculumCourse
    from app.timetable.models.semester import Semester


FeeMapT: TypeAlias = dict[str, Decimal]
FeeLabelMapT: TypeAlias = dict[str, str]
GroupFeeKeyT: TypeAlias = tuple[int, str]


def _semester_start_date(semester: "Semester | None") -> date | None:
    """Return a comparable semester start date."""
    if semester is None:
        return None
    return getattr(semester, "start_date", None)


def resolve_course_fee_group_map(
    course: "Course",
    semester: "Semester | None",
) -> tuple[FeeMapT, FeeLabelMapT]:
    """Return stacked group fees effective for the given semester."""
    semester_start = _semester_start_date(semester)
    if semester_start is None:
        return {}, {}

    groups = getattr(course, "course_fee_groups", None)
    group_ids = (
        list(groups.filter(is_active=True).values_list("id", flat=True))
        if groups is not None
        else []
    )
    if not group_ids:
        return {}, {}

    rules = (
        CourseFeeGroupFee.objects.filter(course_fee_group_id__in=group_ids)
        .select_related("fee_type", "effective_from_semester")
        .order_by(
            "course_fee_group_id",
            "fee_type__code",
            "effective_from_semester__start_date",
            "id",
        )
    )

    latest_rules: dict[GroupFeeKeyT, CourseFeeGroupFee] = {}
    for rule in rules:
        effective_start = _semester_start_date(rule.effective_from_semester)
        if effective_start is None or effective_start > semester_start:
            continue
        key: GroupFeeKeyT = (rule.course_fee_group_id, rule.fee_type.code)
        previous = latest_rules.get(key)
        if previous is None:
            latest_rules[key] = rule
            continue
        previous_start = _semester_start_date(previous.effective_from_semester)
        if previous_start is None or effective_start >= previous_start:
            latest_rules[key] = rule

    fee_map: FeeMapT = {}
    label_map: FeeLabelMapT = {}
    for rule in latest_rules.values():
        fee_code = rule.fee_type.code
        fee_map[fee_code] = fee_map.get(fee_code, Decimal("0.00")) + rule.amount
        label_map[fee_code] = rule.fee_type.label or fee_code

    return fee_map, label_map


class CourseFeeGroup(models.Model):
    """Bundle of courses that share the same semester-effective fee rules."""

    name = models.CharField(max_length=80, unique=True)
    courses = models.ManyToManyField(
        "academics.Course",
        related_name="course_fee_groups",
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    info = models.TextField(blank=True, default="")
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Course fee group"
        verbose_name_plural = "Course fee groups"


class CourseFeeGroupFee(models.Model):
    """Fee type amount for a course fee group effective from a semester."""

    course_fee_group = models.ForeignKey(
        "finance.CourseFeeGroup",
        on_delete=models.CASCADE,
        related_name="fee_rules",
    )
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.CASCADE,
        related_name="course_fee_group_fees",
        default="other",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        related_name="course_fee_group_fees",
    )
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        """Ensure fee_type exists before saving."""
        FeeType.objects.get_or_create(code=self.fee_type_id)
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course_fee_group", "fee_type", "effective_from_semester"],
                name="uniq_group_fee_type_effective_sem",
            )
        ]
        ordering = ["course_fee_group", "effective_from_semester", "fee_type"]


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
    def resolve_amount(
        cls,
        course: "Course",
        semester: "Semester | None",
    ) -> Decimal:
        """Return stacked course-level fees effective for a semester."""
        default_fees = cls.objects.filter(course=course, semester__isnull=True)
        semester_fees = (
            cls.objects.filter(course=course, semester=semester)
            if semester
            else cls.objects.none()
        )
        fee_map: FeeMapT = {}
        for fee in default_fees:
            if not fee.fee_type_id:
                continue
            fee_map[fee.fee_type.code] = fee.amount
        for fee in semester_fees:
            if not fee.fee_type_id:
                continue
            fee_map[fee.fee_type.code] = fee.amount
        group_fee_map, _ = resolve_course_fee_group_map(course, semester)
        fee_map.update(group_fee_map)
        return sum(fee_map.values(), Decimal("0.00"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "fee_type"],
                name="uniq_course_fee_type_per_semester",
            ),
            models.UniqueConstraint(
                fields=["course", "fee_type"],
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
    def resolve_amount(
        cls,
        curriculum_course: "CurriculumCourse",
        semester: "Semester | None",
    ) -> Decimal:
        """Return stacked curriculum+course fees effective for a semester."""
        return curriculum_course.total_fee(semester) - curriculum_course.tuition_for()

    @classmethod
    def total_fee(
        cls,
        curriculum_course: "CurriculumCourse",
        semester: "Semester",
    ) -> Decimal:
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
                fields=["curriculum_course", "semester", "fee_type"],
                name="uniq_curriculum_course_fee_type_per_semester",
            ),
            models.UniqueConstraint(
                fields=["curriculum_course", "fee_type"],
                condition=Q(semester__isnull=True),
                name="uniq_curriculum_course_fee_type_default",
            ),
        ]
        ordering = ["curriculum_course", "semester"]
