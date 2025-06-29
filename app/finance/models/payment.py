"""Payment module."""

from __future__ import annotations

from django.db import models

from app.finance.choices import PaymentMethod


class Payment(models.Model):
    """Payment made for a program.

    Attributes:
        program (academics.Program): A Course in a Curriculum being paid for.
        amount (Decimal): Value of the transaction.
        method (str): Payment method from :class:PaymentMethod.
        recorded_by (people.Staff): Staff member who logged the payment.
        created_at (datetime): Timestamp when the record was created.

    Example:
        >>> from decimal import Decimal
        >>> Payment.objects.create(
        ...     program=program,
        ...     amount=Decimal("50.00"),
        ...     method=PaymentMethod.CASH,
        ...     recorded_by=staff,
        >>> Payment.objects.create(
        ...     program=program,
        ...     amount=Decimal("10.00"),
        ...     method=PaymentMethod.CASH,
        ... )
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    program = models.OneToOneField("academics.Program", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)

    # ~~~~~~~~ Optional ~~~~~~~~
    recorded_by = models.ForeignKey("people.Staff", null=True, on_delete=models.SET_NULL)

    # ~~~~ Auto-filled ~~~~
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        """Return a concise representation of the payment."""
        return f"{self.program} - {self.amount}"
