"""Fee stack models for reusable course fee bundles."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, TypeAlias

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

if TYPE_CHECKING:
    from app.timetable.models.semester import Semester


FeeTypeCodeSetT: TypeAlias = set[str]
FeeMapT: TypeAlias = dict[str, Decimal]
FeeLabelMapT: TypeAlias = dict[str, str]


def _fee_type_codes_for_stack(stack_id: int) -> FeeTypeCodeSetT:
    """Return fee type codes defined on one fee stack."""
    return set(
        FeeStackLine.objects.filter(fee_stack_id=stack_id).values_list(
            "fee_type__code", flat=True
        )
    )


def _semester_start_date(semester: "Semester | None") -> date | None:
    """Return semester start date for comparisons."""
    if semester is None:
        return None
    return getattr(semester, "start_date", None)


def _ranges_overlap(
    first_start: date,
    first_end: date | None,
    second_start: date,
    second_end: date | None,
) -> bool:
    """Return True when two date ranges overlap (inclusive)."""
    first_upper = first_end or date.max
    second_upper = second_end or date.max
    return first_start <= second_upper and second_start <= first_upper


def resolve_course_fee_stack_map(course, semester) -> tuple[FeeMapT, FeeLabelMapT]:
    """Return fee amounts/labels resolved from course stacks active in a semester."""
    semester_start = _semester_start_date(semester)
    if semester_start is None:
        return {}, {}

    fee_map: FeeMapT = {}
    label_map: FeeLabelMapT = {}
    stack_links_manager = getattr(course, "course_fee_stacks", None)
    stack_links = (
        list(
            stack_links_manager.select_related(
                "effective_from_semester",
                "effective_to_semester",
                "fee_stack",
            ).prefetch_related("fee_stack__fees__fee_type")
        )
        if stack_links_manager is not None
        else list(
            CourseFeeStack.objects.filter(course=course)
            .select_related(
                "effective_from_semester",
                "effective_to_semester",
                "fee_stack",
            )
            .prefetch_related("fee_stack__fees__fee_type")
        )
    )
    for stack_link in stack_links:
        link_start = _semester_start_date(stack_link.effective_from_semester)
        link_end = _semester_start_date(stack_link.effective_to_semester)
        if link_start is None or link_start > semester_start:
            continue
        if link_end is not None and link_end < semester_start:
            continue
        for fee_line in stack_link.fee_stack.fees.all():
            fee_type_code = fee_line.fee_type.code
            # Defensive add to keep totals correct even if legacy duplicates exist.
            fee_map[fee_type_code] = fee_map.get(fee_type_code, Decimal("0.00")) + (
                fee_line.amount
            )
            label_map[fee_type_code] = fee_line.fee_type.label or fee_type_code
    return fee_map, label_map


def _fee_type_codes_for_course_stacks(
    course_id: int,
    effective_start: date,
    effective_end: date | None,
    exclude_link_id: int | None,
) -> FeeTypeCodeSetT:
    """Return fee type codes attached to a course in overlapping time windows."""
    stack_links = CourseFeeStack.objects.filter(course_id=course_id).select_related(
        "effective_from_semester",
        "effective_to_semester",
    )
    if exclude_link_id:
        stack_links = stack_links.exclude(pk=exclude_link_id)
    linked_stack_ids: list[int] = []
    for stack_link in stack_links:
        link_start = _semester_start_date(stack_link.effective_from_semester)
        if link_start is None:
            continue
        link_end = _semester_start_date(stack_link.effective_to_semester)
        if not _ranges_overlap(
            first_start=effective_start,
            first_end=effective_end,
            second_start=link_start,
            second_end=link_end,
        ):
            continue
        linked_stack_ids.append(stack_link.fee_stack_id)
    if not linked_stack_ids:
        return set()
    return set(
        FeeStackLine.objects.filter(fee_stack_id__in=linked_stack_ids).values_list(
            "fee_type__code", flat=True
        )
    )


class FeeStack(models.Model):
    """Named reusable set of fee lines that can be attached to many courses."""

    name = models.CharField(max_length=120, unique=True)
    courses = models.ManyToManyField(
        "academics.Course",
        through="finance.CourseFeeStack",
        related_name="fee_stacks",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def total_amount(self) -> Decimal:
        """Return the sum of all fee line amounts in this stack."""
        total = self.fees.aggregate(total=Sum("amount")).get("total")
        return Decimal(total or Decimal("0.00"))

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    class Meta:
        ordering = ["name"]


class FeeStackLine(models.Model):
    """Fee line in a fee stack defined by fee type and amount."""

    fee_stack = models.ForeignKey(
        "finance.FeeStack",
        on_delete=models.CASCADE,
        related_name="fees",
    )
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.PROTECT,
        related_name="fee_stack_lines",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.fee_stack} | {self.fee_type.code} | {self.amount}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fee_stack", "fee_type"],
                name="uniq_fee_type_per_fee_stack",
            )
        ]
        ordering = ["fee_stack", "fee_type"]


class CourseFeeStack(models.Model):
    """Attachment between a course and a fee stack."""

    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.CASCADE,
        related_name="course_fee_stacks",
    )
    fee_stack = models.ForeignKey(
        "finance.FeeStack",
        on_delete=models.CASCADE,
        related_name="course_fee_stacks",
    )
    effective_from_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        related_name="course_fee_stacks_from",
    )
    effective_to_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_fee_stacks_to",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def clean(self) -> None:
        """Block stack attachments that duplicate fee types on the same course."""
        super().clean()
        if not self.course_id or not self.fee_stack_id:
            return

        effective_start = _semester_start_date(self.effective_from_semester)
        if effective_start is None:
            raise ValidationError(
                {"effective_from_semester": "Effective from semester is required."}
            )
        effective_end = _semester_start_date(self.effective_to_semester)
        if effective_end is not None and effective_end < effective_start:
            raise ValidationError(
                {
                    "effective_to_semester": (
                        "Effective to semester cannot be before effective from semester."
                    )
                }
            )

        target_codes = _fee_type_codes_for_stack(self.fee_stack_id)
        if not target_codes:
            return
        linked_codes = _fee_type_codes_for_course_stacks(
            course_id=self.course_id,
            effective_start=effective_start,
            effective_end=effective_end,
            exclude_link_id=self.pk,
        )
        conflicting_codes = sorted(target_codes.intersection(linked_codes))
        if not conflicting_codes:
            return

        code_list = ", ".join(conflicting_codes)
        raise ValidationError(
            {
                "fee_stack": (
                    "Cannot attach this fee stack because the course already has "
                    f"these fee types from other stacks: {code_list}."
                )
            }
        )

    def save(self, *args, **kwargs):
        """Validate fee-type overlap rules before persisting the link."""
        # Keep this invariant at app level even when writes bypass ModelForms.
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.course} -> {self.fee_stack}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "fee_stack", "effective_from_semester"],
                name="uniq_fee_stack_per_course_and_start_semester",
            )
        ]
        ordering = ["course", "effective_from_semester", "fee_stack"]
