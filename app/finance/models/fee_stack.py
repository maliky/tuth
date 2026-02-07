"""Fee stack models for reusable course fee bundles."""

from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords


FeeTypeCodeSetT: TypeAlias = set[str]


def _fee_type_codes_for_stack(stack_id: int) -> FeeTypeCodeSetT:
    """Return fee type codes defined on one fee stack."""
    return set(
        FeeStackLine.objects.filter(fee_stack_id=stack_id).values_list(
            "fee_type__code", flat=True
        )
    )


def _fee_type_codes_for_course_stacks(
    course_id: int,
    exclude_link_id: int | None,
) -> FeeTypeCodeSetT:
    """Return fee type codes already attached to a course via other stacks."""
    stack_links = CourseFeeStack.objects.filter(course_id=course_id)
    if exclude_link_id:
        stack_links = stack_links.exclude(pk=exclude_link_id)
    linked_stack_ids = stack_links.values_list("fee_stack_id", flat=True)
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
        linked_codes = _fee_type_codes_for_course_stacks(self.course_id, self.pk)
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
