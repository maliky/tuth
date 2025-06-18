"""Payment module."""

from __future__ import annotations

from django.db import models

from app.shared.constants import PaymentMethod


class Payment(models.Model):
    """Payment made for a reservation.

    Attributes:
        reservation (timetable.Reservation): Reservation being paid for.
        amount (Decimal): Value of the transaction.
        method (str): Payment method from :class:`PaymentMethod`.
        recorded_by (people.Staff): Staff member who logged the payment.
        created_at (datetime): Timestamp when the record was created.

    Example:
        >>> from decimal import Decimal
        >>> Payment.objects.create(
        ...     reservation=reservation,
        ...     amount=Decimal("50.00"),
        ...     method=PaymentMethod.CASH,
        ...     recorded_by=staff,
        ... )
    """

    reservation = models.OneToOneField("timetable.Reservation", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    recorded_by = models.ForeignKey("people.Staff", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        """Return a concise representation of the payment."""
        return f"{self.reservation} - {self.amount}"
