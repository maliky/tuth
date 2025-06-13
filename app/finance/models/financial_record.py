"""Financial record module."""

from __future__ import annotations

from django.db import models

from app.shared.constants.finance import FeeType, StatusClearance


class FinancialRecord(models.Model):
    """Aggregate balance for a student."""

    student = models.OneToOneField("people.Student", on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    clearance_status = models.CharField(
        max_length=50,
        choices=StatusClearance.choices,
        default="pending",
    )
    last_updated = models.DateTimeField(auto_now=True)
    verified_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_records_verified",
    )


class SectionFee(models.Model):
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    fee_type = models.CharField(max_length=50, choices=FeeType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
