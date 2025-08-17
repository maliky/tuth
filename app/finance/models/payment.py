"""Financial record module."""

from __future__ import annotations

from typing import Self

from app.shared.status.mixins import StatusableMixin
from django.db import models
from simple_history.models import HistoricalRecords

from app.shared.mixins import SimpleTableMixin


class ClearanceStatus(SimpleTableMixin):
    """Clearance Statuses."""

    # PENDING = "pending", "Pending"
    # CLEARED = "cleared", "Cleared"
    # BLOCKED = "blocked", "Blocked"

    DEFAULT_VALUES = ["pending", "cleared", "blocked"]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default ClearanceStatus."""

        deft, _ = cls.objects.get_or_create(code="pending")
        return deft


class PaymentMethod(SimpleTableMixin):
    """Payment method statuses."""

    # CASH = "cash", "Cash"
    # CRYPTO = "crypto", "Crypto (ADA)"
    # MOBILE_MONEY = "mobile_money", "Mobile Money"
    # WIRE = "wire", "Wire"
    DEFAULT_VALUES = ["wire", "mobile Money", "crypto_ada", "cash"]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default PaymentMethod."""
        deft, _ = cls.objects.get_or_create(code="cash")
        return deft


class FeeType(SimpleTableMixin):
    """Enumeration of fee types."""

    # CREDIT_HOUR_FEE = "CREDIT_HOUR_FEE", "Credit Hour Fee"
    # LAB = "lab", "Lab"
    # OTHER = "other", "Other"
    # RESEARCH = "research", "Research"
    # TUITION = "tuition", "Tuition"
    DEFAULT_VALUES = [
        "tuition",
        "research",
        "other",
        "lab",
        "credit_hour_fee",
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code="other")
        return deft


class Payment(StatusableMixin, models.Model):
    """Payment for an Invoice by a student.

    Store the payments made by students
    The payment have a status can be pending (eg. wire transfert)

    Attributes:
        invoice
        amount_paid
        payment_method
        status (payment)
        recorded_by (staff)
        history : track any change made to a payment

    Payment can be created by students but they have a pending status and are only counted
    when verified by authorized staff.

    Example:
        >>> from decimal import Decimal
        >>> Payment.objects.create(
        ...     student=student,
        ...     total_due=Decimal("500.00"),
        ... )
        >>> Payment.objects.create(student=student_profile, total_due=0)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    invoice = models.ForeignKey(
        "finance.Invoice",
        on_delete=models.PROTECT,
        related_name="payments",
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

    @property
    def balance_due(self):
        """Compute the balance amount for this payement."""
        return self.invoice.amount_due - self.amount_paid

    def _ensure_payment_method(self):
        """Ensure that we have a payment method set otherway create a default one."""
        if not self.payment_method_id:
            self.payment_method = PaymentMethod.get_default()

    def _ensure_status(self):
        """Ensure that we have a ClearanceStatus set otherway create a default one."""
        if not self.status_id:
            self.status = ClearanceStatus.get_default()

    def save(self, *args, **kwargs):
        """Ensure the status exist befor saving."""
        self._ensure_payment_method()
        self._ensure_status()
        return super().save(*args, **kwargs)


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
        return super().save(*args, **kwargs)
