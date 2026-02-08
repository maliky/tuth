"""Fee stack models for reusable course fee bundles."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, TypeAlias

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

if TYPE_CHECKING:
    from app.timetable.models.semester import Semester


FeeTypeCodeSetT: TypeAlias = set[str]
FeeMapT: TypeAlias = dict[str, Decimal]
FeeLabelMapT: TypeAlias = dict[str, str]
PayerCodeSetT: TypeAlias = set[str]
PAYER_STUDENT_CODE = "student"


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


def _is_newer_start(candidate: date | None, current: date | None) -> bool:
    """Return True when candidate start date is more recent than current."""
    return (candidate or date.min) > (current or date.min)


def _resolve_stack_fee_lines_for_semester(
    fee_lines,
    semester_start: date | None,
) -> list["FeeStackLine"]:
    """Pick one fee line per fee type using latest effective_from <= semester."""
    selected_lines: dict[str, FeeStackLine] = {}
    selected_starts: dict[str, date | None] = {}
    for fee_line in fee_lines:
        line_start = _semester_start_date(fee_line.effective_from_semester)
        if (
            semester_start is not None
            and line_start is not None
            and line_start > semester_start
        ):
            continue
        fee_type_code = fee_line.fee_type.code
        if fee_type_code not in selected_lines or _is_newer_start(
            line_start, selected_starts.get(fee_type_code)
        ):
            selected_lines[fee_type_code] = fee_line
            selected_starts[fee_type_code] = line_start
    return list(selected_lines.values())


def _resolve_line_payer(
    fee_line: "FeeStackLine",
    fallback_payer: str | None,
) -> str:
    """Resolve one line payer using line -> stack -> fallback order."""
    return (
        fee_line.payer_id
        or fee_line.fee_stack.payer_id
        or fallback_payer
        or PAYER_STUDENT_CODE
    )


def resolve_fee_stack_line_payers(
    fee_stacks: list["FeeStack"],
    semester: "Semester | None",
    fallback_payer: str | None,
) -> PayerCodeSetT:
    """Return resolved payer codes for attached fee stacks and semester context."""
    semester_start = _semester_start_date(semester)
    payer_codes: PayerCodeSetT = set()
    for fee_stack in fee_stacks:
        resolved_lines = _resolve_stack_fee_lines_for_semester(
            fee_stack.fees.select_related("fee_type", "effective_from_semester"),
            semester_start,
        )
        for fee_line in resolved_lines:
            payer_codes.add(_resolve_line_payer(fee_line, fallback_payer))
    return payer_codes


def _refresh_parent_invoices_for_stack(stack_id: int | None) -> None:
    """Refresh parent invoice totals affected by one fee-stack change."""
    if stack_id is None:
        return
    from app.finance.models.invoice import StudentSemesterInvoice

    parent_invoices = StudentSemesterInvoice.objects.filter(
        fee_stacks__id=stack_id
    ).distinct()
    for parent_invoice in parent_invoices:
        parent_invoice.refresh_totals_from_sources(save_model=True)


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
            stack_links_manager.select_related("fee_stack").prefetch_related(
                "fee_stack__fees__fee_type",
                "fee_stack__fees__effective_from_semester",
            )
        )
        if stack_links_manager is not None
        else list(
            CourseFeeStack.objects.filter(course=course)
            .select_related("fee_stack")
            .prefetch_related(
                "fee_stack__fees__fee_type",
                "fee_stack__fees__effective_from_semester",
            )
        )
    )
    for stack_link in stack_links:
        for fee_line in _resolve_stack_fee_lines_for_semester(
            stack_link.fee_stack.fees.all(),
            semester_start,
        ):
            fee_type_code = fee_line.fee_type.code
            # Defensive add to keep totals correct even if legacy duplicates exist.
            fee_map[fee_type_code] = fee_map.get(fee_type_code, Decimal("0.00")) + (
                fee_line.amount
            )
            label_map[fee_type_code] = fee_line.fee_type.label or fee_type_code
    return fee_map, label_map


def _fee_type_codes_for_course_stacks(
    course_id: int,
    exclude_link_id: int | None,
) -> FeeTypeCodeSetT:
    """Return fee type codes attached to a course via other stacks."""
    stack_links = CourseFeeStack.objects.filter(course_id=course_id)
    if exclude_link_id:
        stack_links = stack_links.exclude(pk=exclude_link_id)
    linked_stack_ids = list(stack_links.values_list("fee_stack_id", flat=True))
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
    payer = models.ForeignKey(
        "finance.Payer",
        on_delete=models.PROTECT,
        related_name="fee_stacks",
        null=True,
        blank=True,
    )
    courses = models.ManyToManyField(
        "academics.Course",
        through="finance.CourseFeeStack",
        related_name="fee_stacks",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def total_amount_for_semester(self, semester: "Semester | None") -> Decimal:
        """Return stack amount for one semester using line effective dates."""
        semester_start = _semester_start_date(semester)
        resolved_lines = _resolve_stack_fee_lines_for_semester(
            self.fees.select_related("fee_type", "effective_from_semester"),
            semester_start,
        )
        return sum((line.amount for line in resolved_lines), Decimal("0.00"))

    def total_amount(self) -> Decimal:
        """Return stack amount as of the latest configured effective lines."""
        return self.total_amount_for_semester(semester=None)

    def save(self, *args, **kwargs):
        """Save the stack and refresh parent invoice aggregates."""
        save_result = super().save(*args, **kwargs)
        _refresh_parent_invoices_for_stack(self.pk)
        return save_result

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
    payer = models.ForeignKey(
        "finance.Payer",
        on_delete=models.PROTECT,
        related_name="fee_stack_lines",
        null=True,
        blank=True,
    )
    effective_from_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fee_stack_lines",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def clean(self) -> None:
        """Enforce one baseline line and require baseline before dated lines."""
        super().clean()
        if not self.fee_stack_id or not self.fee_type_id:
            return

        default_qs = FeeStackLine.objects.filter(
            fee_stack_id=self.fee_stack_id,
            fee_type_id=self.fee_type_id,
            effective_from_semester__isnull=True,
        ).exclude(pk=self.pk)
        if self.effective_from_semester_id is None:
            if default_qs.exists():
                raise ValidationError(
                    {
                        "effective_from_semester": (
                            "Only one default fee line (no effective from semester) "
                            "is allowed for a fee stack and fee type."
                        )
                    }
                )
            return

        if not default_qs.exists():
            raise ValidationError(
                {
                    "effective_from_semester": (
                        "Create a default fee line with no effective from semester "
                        "before adding dated fee lines."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Validate effective-semester rules before saving a fee line."""
        self.full_clean()
        save_result = super().save(*args, **kwargs)
        _refresh_parent_invoices_for_stack(self.fee_stack_id)
        return save_result

    def delete(self, *args, **kwargs):
        """Refresh parent invoice aggregates after deleting a fee line."""
        stack_id = self.fee_stack_id
        delete_result = super().delete(*args, **kwargs)
        _refresh_parent_invoices_for_stack(stack_id)
        return delete_result

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"{self.fee_stack} | {self.fee_type.code} | {self.amount}"
            f" | from {self.effective_from_semester or 'default'}"
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fee_stack", "fee_type", "effective_from_semester"],
                name="uniq_fee_type_per_stack_and_start_semester",
            )
        ]
        ordering = ["fee_stack", "fee_type", "effective_from_semester"]


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def clean(self) -> None:
        """Block stack attachments that duplicate fee types on the same course."""
        super().clean()
        if not self.course_id or not self.fee_stack_id:
            return

        target_codes = _fee_type_codes_for_stack(self.fee_stack_id)
        if not target_codes:
            return
        linked_codes = _fee_type_codes_for_course_stacks(
            course_id=self.course_id,
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
                fields=["course", "fee_stack"],
                name="uniq_fee_stack_per_course",
            )
        ]
        ordering = ["course", "fee_stack"]
