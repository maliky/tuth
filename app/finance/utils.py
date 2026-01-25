"""Utility helpers used in the finance app."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Optional

from django.db import transaction

if TYPE_CHECKING:
    from app.academics.models.course import CurriculumCourse
    from app.people.models.staffs import Staff

from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment


PaymentCreateSummaryT = dict[str, int]


TUITION_RATE_PER_CREDIT = Decimal("5.00")


def tuition_for(curriculum_course: "CurriculumCourse") -> Decimal:
    """Calculate the tuition amount for a curriculum course.

    Args:
        curriculum_course: Curriculum course carrying the credit hour value.

    Returns:
        The total tuition cost.

    Examples:
        With 3 credit hours at the current rate, the result is 15.00.
    """
    credit_hours = getattr(curriculum_course, "credit_hours", None)
    credit_code = getattr(credit_hours, "code", None)

    return Decimal(int(credit_code or 0)) * TUITION_RATE_PER_CREDIT


def create_pending_payments(
    invoices: Iterable[Invoice],
    recorded_by: Optional["Staff"] = None,
) -> PaymentCreateSummaryT:
    """Create pending payments for invoices when none exist.

    Args:
        invoices: Iterable of invoices to receive pending payments.
        recorded_by: Optional staff profile to attach to created payments.

    Returns:
        Summary counts for created and skipped payments.
    """
    summary: PaymentCreateSummaryT = {
        "created": 0,
        "skipped_existing": 0,
        "skipped_closed": 0,
    }
    invoice_list = list(invoices)
    if not invoice_list:
        return summary
    with transaction.atomic():
        for invoice in invoice_list:
            if invoice.balance <= 0:
                summary["skipped_closed"] += 1
                continue
            if Payment.objects.filter(
                invoice=invoice,
                status_id="pending",
            ).exists():
                summary["skipped_existing"] += 1
                continue
            Payment.objects.create(
                invoice=invoice,
                amount_paid=invoice.balance,
                recorded_by=recorded_by,
            )
            summary["created"] += 1
    return summary
