from __future__ import (
    annotations,
)  # to postpone evaluation of type hints

from django.contrib.auth.models import User
from django.db import models

from app.shared.constants import CLEARANCE_CHOICES
from app.shared.utils import make_choices


class FinancialRecord(models.Model):
    """Aggregate balance for a student."""

    student = models.OneToOneField(User, on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    clearance_status = models.CharField(
        max_length=50,
        choices=make_choices(CLEARANCE_CHOICES),
        default="pending",
    )
    last_updated = models.DateTimeField(auto_now=True)
    verified_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_records_verified",
    )
