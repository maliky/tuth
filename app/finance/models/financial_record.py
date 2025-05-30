from __future__ import (
    annotations,
)  # to postpone evaluation of type hints


from django.db import models

from app.shared.constants import CLEARANCE_CHOICES
from app.shared.constants.finance import FeeTypeLabels
from app.shared.utils import make_choices


class FinancialRecord(models.Model):
    """Aggregate balance for a student."""

    student = models.OneToOneField("people.StudentProfile", on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    clearance_status = models.CharField(
        max_length=50,
        choices=make_choices(CLEARANCE_CHOICES),
        default="pending",
    )
    last_updated = models.DateTimeField(auto_now=True)
    verified_by = models.ForeignKey(
        "people.StaffProfile",
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_records_verified",
    )


class FeeType(models.Model):
    # > Add this as a TextChoices ins constants.choices
    # > list the type extensively
    # > a specialy feetype is the credit_hour_fee, it is then use to compute the Course amount
    # e.g. are Tuition, Lab, Research, etc.
    name = models.CharField(max_length=50, choices=FeeTypeLabels.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


class SectionFee(models.Model):
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    fee_type = models.ForeignKey(FeeType, on_delete=models.CASCADE)
