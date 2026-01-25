"""Financial record module."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models, transaction
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import PaymentStatus
from app.shared.status.mixins import StatusableMixin

if TYPE_CHECKING:
    from app.finance.models.invoice import Invoice


class Payment(StatusableMixin, models.Model):
    """Payment for an Invoice by a student.

    Store the payments made by students. The payment have default pending status.
    Payment can only be created by authorized staff.

    Attributes:
        invoice: Invoice linked to the payment.
        amount_paid: Amount recorded for the payment.
        recorded_by: Staff member who logged the payment.

    Example:
        >>> from app.finance.models.invoice import Invoice
        >>> invoice = Invoice.get_default()
        >>> invoice.save(update_fields=["initial_amount_due", "balance"])
        >>> Payment.objects.create(invoice=invoice)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    invoice = models.ForeignKey(
        "finance.Invoice", on_delete=models.PROTECT, related_name="payments"
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # ~~~~ Auto-filled ~~~~
    payment_method = models.ForeignKey(
        "finance.PaymentMethod",
        on_delete=models.PROTECT,
        related_name="payments",
        default="cash",
    )
    status = models.ForeignKey(
        "finance.ClearanceStatus",
        on_delete=models.PROTECT,
        related_name="payments",
        default="pending",
    )

    history = HistoricalRecords()
    # ~~~~~~~~ Optional ~~~~~~~~
    recorded_by = models.ForeignKey(
        "people.Staff",
        on_delete=models.SET_NULL,
        related_name="payments_recorded",
        null=True,
    )

    def _update_invoice_balance(self) -> None:
        """Update the invoice balance to reflect cleared payments."""
        new_amount = self.invoice.balance - self.amount_paid
        if new_amount < 0:
            new_amount = Decimal("0.00")
        self.invoice.balance = new_amount
        self.invoice.save(update_fields=["balance"])

    def _ensure_payment_method(self):
        """Ensure that we have a method set, otherway create a default one."""
        if not self.payment_method_id:
            self.payment_method = PaymentMethod.get_default()

    def _ensure_status(self):
        """Ensure that we have a status set, otherway create a default one."""
        if not self.status_id:
            self.status = PaymentStatus.get_default()

    def save(self, *args, **kwargs):
        """Ensure the status exists before saving."""
        self._ensure_payment_method()
        self._ensure_status()
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            # the invoice must exist before the invoice.
            self._update_invoice_balance()
            # Update registrations once cleared payments reach the threshold.
            _update_registration_status(self.invoice)
        return result


# See where to move this function to avoid Model import in the function body
def _update_registration_status(invoice: "Invoice") -> int:
    """Update registration status when the invoice is settled."""
    if not invoice:
        return 0
    # Align registration clearance with the invoice status instead of payment totals.
    if invoice.status_id != "settled":
        return 0
    from app.registry.models.registration import Registration, RegistrationStatus

    cleared_status, _ = RegistrationStatus.objects.get_or_create(
        code="cleared",
        defaults={"label": "Financially Cleared"},
    )
    return (
        Registration.objects.filter(
            student=invoice.student,
            section__curriculum_course=invoice.curriculum_course,
            section__semester=invoice.semester,
        )
        .exclude(status=cleared_status)
        .update(status=cleared_status)
    )
