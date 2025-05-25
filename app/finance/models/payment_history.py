from __future__ import (
    annotations,
)  # to postpone evaluation of type hints

from django.contrib.auth.models import User
from django.db import models


class PaymentHistory(models.Model):
    """Individual payment made toward a financial record."""

    financial_record = models.ForeignKey(
        "finance.FinancialRecord", related_name="payments", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=50, blank=True)  # cash, bank, mobile …
    recorded_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="payments_recorded"
    )
