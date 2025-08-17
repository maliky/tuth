"""Payment history module."""

from __future__ import annotations  # to postpone evaluation of type hints

from app.finance.choices import PaymentMethod
from django.db import models
from simple_history.models import HistoricalRecords


class PaymentHistory(models.Model):
    """Record of a payment against a financial record.

    This model keeps a log of every payment for auditing purposes. No signals
    are currently attached.

    Attributes:
        financial_record (finance.FinancialRecord): Record the payment belongs to.
        amount (Decimal): Amount paid.
        payment_date (datetime): Timestamp when the payment was recorded.
        method (str): Optional textual description of the method used.
        recorded_by (people.Staff): Staff user who entered the payment.

    Example:
        >>> from decimal import Decimal
        >>> PaymentHistory.objects.create(
        ...     financial_record=PaymentRecord.get_default(),
        ...     amount=Decimal("25.00"),
        ...     method=P"cash",
        ... )
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    financial_record = models.ForeignKey(
        "finance.FinancialRecord", related_name="payments", on_delete=models.CASCADE
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)

    # ~~~~ Auto-filled ~~~~
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.ForeignKey(
        "finance.PaymentMethod",
        on_delete=models.PROTECT,
        related_name="payments_recorded",
    )
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    recorded_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
        related_name="payments_recorded",
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return "amount on date for student" for admin readability."""
        return f"{self.amount_paid} on {self.payment_date_str} for {self.financial_record.student}"

    def save(self, *arg, **kwargs) -> None:
        """Set default before saving."""
        if not self.payment_method_id:
            self.payment_method = PaymentMethod.get_default()

    @property
    def payment_date_str(self) -> str:
        """Get the payment date as HH:MM:SS formated string."""
        return self.payment_date.strftime("%H:%M:%S")

    class Meta:
        ordering = ["-payment_date"]
