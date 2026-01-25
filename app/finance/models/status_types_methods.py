"""Financial Types and status."""

# > When is this import necessary
from __future__ import annotations

from typing import Self, cast

from django.db import models

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


class InvoiceStatus(SimpleTableMixin):
    """Clearance Statuses for invoices."""

    # this is not realy meant to be editable by users
    # Here for convenience
    DEFAULT_VALUES = [
        ("initial", "Initial"),
        ("settled", "Settled"),
        ("cleared", "Cleared"),
        ("updated", "Updated"),
    ]

    class Meta:
        verbose_name = "Invoice Status"
        verbose_name_plural = "Invoice Status"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default ClearanceStatus."""
        deft, _ = cls.objects.get_or_create(code="initial")
        return cast(Self, deft)


class PaymentStatus(SimpleTableMixin):
    """Clearance Statuses for payment."""

    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("cleared", "Cleared"),
        ("blocked", "Blocked"),
    ]

    class Meta:
        verbose_name = "Payment Status"
        verbose_name_plural = "Payment Status"

    @classmethod
    def get_default(cls) -> Self:
        """Returns the default PaymentStatus."""
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
