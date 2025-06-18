"""Financial record module."""

from __future__ import annotations

from django.db import models

from app.shared.constants.finance import FeeType, StatusClearance


class FinancialRecord(models.Model):
    """Financial snapshot for a student.

    Tracks the overall balance and clearance status for a student. Individual
    payments are stored as :class:`~app.finance.models.PaymentHistory` instances
    via the ``payments`` related name.

    Attributes:
        student (people.Student): Owner of the record.
        total_due (Decimal): Total amount owed.
        total_paid (Decimal): Total amount paid.
        clearance_status (str): Whether the student is financially cleared.
        last_updated (datetime): Timestamp of last modification.
        verified_by (people.Staff): Staff member that verified the record.

    Example:
        >>> from decimal import Decimal
        >>> FinancialRecord.objects.create(
        ...     student=student,
        ...     total_due=Decimal("500.00"),
        ... )
    """

    student = models.OneToOneField("people.Student", on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    clearance_status = models.CharField(
        max_length=50,
        choices=StatusClearance.choices,
        default="pending",
    )
    last_updated = models.DateTimeField(auto_now=True)
    verified_by = models.ForeignKey(
        "people.Staff",
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_records_verified",
    )


class SectionFee(models.Model):
    """Additional fee charged for a specific course section.

    Attributes:
        section (timetable.Section): Section the fee applies to.
        fee_type (str): Type of fee as defined in :class:`FeeType`.
        amount (Decimal): Monetary value of the fee.

    Example:
        >>> from decimal import Decimal
        >>> SectionFee.objects.create(
        ...     section=section,
        ...     fee_type=FeeType.LAB,
        ...     amount=Decimal("25.00"),
        ... )
    """

    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    fee_type = models.CharField(max_length=50, choices=FeeType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
