"""Financial record module."""

from __future__ import annotations
from django.core.exceptions import ValidationError
from app.finance.choices import ClearanceStatus, FeeType
from django.db import models
from simple_history.models import HistoricalRecords


class FinancialRecord(models.Model):
    """Financial snapshot for a student.

    Tracks the overall balance and clearance status for a student. Individual
    payments are stored as :class:~app.finance.models.PaymentHistory instances
    via the payments related name.

    Attributes:
        student (people.Student): Owner of the record.
        amount_due (Decimal): Total amount owed.
        amount_paid (Decimal): Total amount paid.
        amount_balance (Decimal): Total amount balance.
        clearance_status (str): Status of the payment (pending, cleared, blocked).
        last_updated (datetime): Timestamp of last modification.
        verified_by (people.Staff): Staff member that verified the record.

    Example:
        >>> from decimal import Decimal
        >>> FinancialRecord.objects.create(
        ...     student=student,
        ...     total_due=Decimal("500.00"),
        ... )
        >>> FinancialRecord.objects.create(student=student_profile, total_due=0)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    student = models.OneToOneField("people.Student", on_delete=models.CASCADE)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)

    # ~~~~ Auto-filled ~~~~
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    status = models.ForeignKey(
        "finance.ClearanceStatus",
        on_delete=models.PROTECT,
        related_name="financial_records",
        default="pending",
    )

    last_updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    verified_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_records_verified",
    )

    def _ensure_clearance_status(self):
        """Ensure a clearance status is set."""
        if not self.status_id:
            self.status = ClearanceStatus.get_default()

    def _ensure_amount_balance(self):
        """Compute the balance amount for this payement."""
        if not self.amount_balance:
            self.amount_balance = self.amount_due - self.amount_paid

    def _ensure_concordance_clearance_balance(self):
        """Make sure the payment is cleared if balance is 0 and vice versa."""
        if self.amount_balance == 0 and self.status != ClearanceStatus.CLEARED:
            raise ValidationError(
                f"clearance_status ({self.status}) should be {ClearanceStatus.CLEARED} when amount_balance is {self.amount_balance}"
            )
        if self.status == ClearanceStatus.CLEARED and self.amount_balance == 0:
            raise ValidationError(
                f"Amount_balance ({self.amount_balance}) should be 0 when clearance status is  {self.status}"
            )

    def save(self, *args, **kwargs):
        """Ensure the status exist befor saving."""
        self._ensure_amount_balance()
        self._ensure_clearance_status()
        self._ensure_concordance_clearance_balance()


class SectionFee(models.Model):
    """Additional fee charged for a specific course section.

    Attributes:
        section (timetable.Section): Section the fee applies to.
        fee_type (str): Type of fee as defined in :class:FeeType.
        amount (Decimal): Monetary value of the fee.

    Example:
        >>> from decimal import Decimal
        >>> SectionFee.objects.create(
        ...     section=section,
        ...     fee_type=FeeType.objects.get(code='lab'),
        ...     amount=Decimal("25.00"),
        ... )
        >>> SectionFee.objects.create(section=section, fee_type=FeeType.LAB, amount=50)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.CASCADE,
        related_name="sections_fees",
        default="other",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        """Ensure the status exist befor saving."""
        FeeType.objects.get_or_create(code=self.fee_type_id)
