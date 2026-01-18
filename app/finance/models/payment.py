"""Financial record module."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Self, cast

from app.shared.status.mixins import StatusableMixin
from django.db import models, transaction
from simple_history.models import HistoricalRecords

from app.shared.mixins import SimpleTableMixin


class AccountType(SimpleTableMixin):
    """Account Types."""

    default_values = [
        ("liability", "Liability"),
        ("asset", "Asset"),
        ("capital", "Capital"),
        ("expense", "Expense"),
        ("income", "Income"),
        ("unknown", "Unknown"),
    ]

    class Meta:
        verbose_name = "Account Type"
        verbose_name_plural = "Account Types"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default AccountType."""
        deft, _ = cls.objects.get_or_create(code="liability")
        return cast(Self, deft)


class AccountChartType(SimpleTableMixin):
    """Account Chart Types."""

    DEFAULT_VALUES = [
        ("account_payable", "Account Payable"),
        ("account_receivable", "Account Receivable"),
        ("Bank", "Bank"),
        ("Cash", "Cash"),
        ("Equity", "Equity"),
        ("Expense", "Expense"),
        ("fixed_asset", "Fixed Asset"),
        ("Income", "Income"),
        ("long_term_liability", "Long Term Liability"),
        ("other_current_asset", "Other Current Asset"),
        ("other_current_liability", "Other Current Liability"),
        ("other", "Other"),
    ]
    # ~~~~~~~~~~~~~~~~ optional ~~~~~~~~~~~~~~~~
    type = models.ForeignKey(
        "finance.AccountType",
        on_delete=models.PROTECT,
        related_name="unknown",
    )

    class Meta:
        verbose_name = "Account Type"
        verbose_name_plural = "Account Types"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default AccountType."""
        deft, _ = cls.objects.get_or_create(code="other")
        return cast(Self, deft)

    @classmethod
    def _populate_attributes_and_db(cls):
        """Ensure default rows are tied to a valid AccountType."""
        account_type = AccountType.get_default()
        for val, lbl in cls.DEFAULT_VALUES:
            cls.objects.get_or_create(
                code=val,
                defaults={
                    "label": lbl,
                    "type": account_type,
                },
            )


class ClearanceStatus(SimpleTableMixin):
    """Clearance Statuses."""

    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("cleared", "Cleared"),
        ("blocked", "Blocked"),
    ]

    class Meta:
        verbose_name = "Clearance Status"
        verbose_name_plural = "Clearance Status"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default ClearanceStatus."""
        deft, _ = cls.objects.get_or_create(code="pending")
        return cast(Self, deft)


class PaymentMethod(SimpleTableMixin):
    """Payment method statuses."""

    DEFAULT_VALUES = [
        ("wire", "Wire"),
        ("mobile", "Mobile Money"),
        ("crypto_ada", "Crypto Ada"),
        ("cash", "Cash"),
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default PaymentMethod."""
        deft, _ = cls.objects.get_or_create(
            code="cash",
        )
        return cast(Self, deft)


class FeeType(SimpleTableMixin):
    """Enumeration of fee types."""

    DEFAULT_VALUES = [
        ("activities", "Activities"),
        ("athletics", "Athletics"),
        ("biology_lab", "Biology Lab"),
        ("chemistry_lab", "Chemistry Lab"),
        ("clinical", "Clinical"),
        ("credit_hour", "Credit Hour"),
        ("dormitory", "Dormitory"),
        ("enterpreneurship", "Enterpreneurship"),
        ("entrepreneurship_education_i", "Entrepreneurship Education I"),
        ("entrepreneurship_education_ii", "Entrepreneurship Education II"),
        ("graduation", "Graduation"),
        ("id_card", "ID Card"),
        ("lab", "Laboratory"),
        ("late_registration", "Late Registration"),
        ("library", "Library"),
        ("maintenance", "Maintenance"),
        ("medical_surgical_lab", "Medical Surgical Lab"),
        ("obstetric_nursing_lab", "Obstetric Nursing Lab"),
        ("other", "Other"),
        ("pe_tshirt", "P.E. T-Shirt"),
        ("pediatric_lab", "Pediatric Lab"),
        ("physics_lab", "Physics Lab"),
        ("pre-registration_penalty", "Pre-Registration Penalty"),
        ("re-admission", "Re-Admission"),
        ("registration", "Registration"),
        ("research", "Research"),
        ("science_laboratory", "Science Laboratory"),
        ("sports", "Sports"),
        ("technology", "Technology"),
        ("transcript", "Transcript"),
        ("tuition", "Tuition"),
    ]

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default FeeType."""
        deft, _ = cls.objects.get_or_create(code="other")
        return cast(Self, deft)


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
        return self.invoice.amount_due

    def _invoice_balance_delta(
        self,
        previous_status_id: Optional[str],
        previous_amount_paid: Decimal,
    ) -> Decimal:
        """Return the delta to apply to the invoice balance."""
        is_cleared = self.status_id == "cleared"
        was_cleared = previous_status_id == "cleared"
        if not is_cleared and not was_cleared:
            return Decimal("0.00")

        current_amount = self.amount_paid or Decimal("0.00")
        previous_amount = previous_amount_paid or Decimal("0.00")
        cleared_delta = (current_amount if is_cleared else Decimal("0.00")) - (
            previous_amount if was_cleared else Decimal("0.00")
        )
        return cleared_delta

    def _update_invoice_balance(
        self,
        previous_status_id: Optional[str],
        previous_amount_paid: Decimal,
    ) -> None:
        """Update the invoice amount_due to reflect cleared payments."""
        if not self.invoice_id:
            return
        delta = self._invoice_balance_delta(previous_status_id, previous_amount_paid)
        if delta == 0:
            return

        new_amount = self.invoice.amount_due - delta
        if new_amount < 0:
            new_amount = Decimal("0.00")
        self.invoice.amount_due = new_amount
        self.invoice.save(update_fields=["amount_due"])

    def _ensure_payment_method(self):
        """Ensure that we have a payment method set otherway create a default one."""
        if not self.payment_method_id:
            self.payment_method = PaymentMethod.get_default()

    def _ensure_status(self):
        """Ensure that we have a ClearanceStatus set otherway create a default one."""
        if not self.status_id:
            self.status = ClearanceStatus.get_default()

    def save(self, *args, **kwargs):
        """Ensure the status exists before saving."""
        previous_status_id: Optional[str] = None
        previous_amount_paid = Decimal("0.00")
        if self.pk:
            previous = (
                Payment.objects.filter(pk=self.pk)
                # Avoid values() TypedDict inference that trips mypy-django.
                .values_list("status_id", "amount_paid").first()
            )
            if previous:
                previous_status_id = previous[0]
                previous_amount_paid = previous[1] or Decimal("0.00")
        self._ensure_payment_method()
        self._ensure_status()
        with transaction.atomic():
            result = super().save(*args, **kwargs)
            # > Are we sure that self.status_id is cleared when we get here ?
            self._update_invoice_balance(previous_status_id, previous_amount_paid)
        return result


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
