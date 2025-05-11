from __future__ import (
    annotations,
)  # to postpone evaluation of type hints

from django.db import models
from django.contrib.auth.models import User
from app.constants import CLEARANCE_CHOICES
from app.models.utils import make_choices


# ─────────── Finance ───────────────────────────────
class FinancialRecord(models.Model):
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


class PaymentHistory(models.Model):
    financial_record = models.ForeignKey(
        "app.FinancialRecord", related_name="payments", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=50, blank=True)  # cash, bank, mobile …
    recorded_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="payments_recorded"
    )
