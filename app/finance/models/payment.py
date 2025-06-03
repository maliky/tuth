"""Payment module."""

from __future__ import annotations

from django.db import models

from app.shared.constants import PaymentMethod


class Payment(models.Model):
    """Payment made for a reservation."""

    reservation = models.OneToOneField("timetable.Reservation", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    recorded_by = models.ForeignKey(
        "people.StaffProfile", null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.reservation} - {self.amount}"
