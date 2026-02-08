"""Financial record module."""

from __future__ import annotations

from django.db import models, transaction
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import PaymentMethod, PaymentStatus
from app.shared.mixins import StatusableMixin


class Payment(StatusableMixin, models.Model):
    """Payment for a student-semester invoice.

    Store the payments made by students. The payment have default pending status.
    Payment can only be created by authorized staff.

    Attributes:
        student_semester_invoice: Parent invoice linked to the payment.
        payer: Party funding the payment.
        amount_paid: Amount recorded for the payment.
        recorded_by: Staff member who logged the payment.

    Example:
        >>> from app.finance.models.invoice import StudentSemesterInvoice
        >>> invoice = StudentSemesterInvoice.objects.first()
        >>> Payment.objects.create(student_semester_invoice=invoice)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    student_semester_invoice = models.ForeignKey(
        "finance.StudentSemesterInvoice",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payer = models.ForeignKey(
        "finance.Payer",
        on_delete=models.PROTECT,
        related_name="payments",
        default="student",
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # ~~~~ Auto-filled ~~~~
    payment_method = models.ForeignKey(
        "finance.PaymentMethod",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
        default=None,
    )
    status = models.ForeignKey(
        "finance.PaymentStatus",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
        default=None,
    )

    history = HistoricalRecords()
    # ~~~~~~~~ Optional ~~~~~~~~
    recorded_by = models.ForeignKey(
        "people.Staff",
        on_delete=models.SET_NULL,
        related_name="payments_recorded",
        null=True,
    )

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
            # Payment edits must keep the parent invoice totals in sync.
            self.student_semester_invoice.refresh_totals_from_sources(save_model=True)
        return result

    def delete(self, *args, **kwargs):
        """Keep parent invoice totals in sync after payment deletion."""
        parent_invoice = self.student_semester_invoice
        with transaction.atomic():
            result = super().delete(*args, **kwargs)
            parent_invoice.refresh_totals_from_sources(save_model=True)
        return result
