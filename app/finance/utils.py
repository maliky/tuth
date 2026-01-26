"""Utility helpers used in the finance app."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Optional

from django.db import transaction

if TYPE_CHECKING:
    from app.academics.models.curriculum_course import CurriculumCourse
    from app.people.models.staffs import Staff

from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment


PaymentCreateSummaryT = dict[str, int]


def create_pending_payments(
    invoices: Iterable[Invoice],
    recorded_by: Optional["Staff"] = None,
) -> PaymentCreateSummaryT:
    """Create pending full payments for invoices when none exist.

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
            balance = invoice.get_balance()
            if balance <= 0:
                summary["skipped_closed"] += 1
                continue
            if Payment.objects.filter(invoice=invoice, status_id="pending").exists():
                summary["skipped_existing"] += 1
                continue
            Payment.objects.create(
                invoice=invoice, amount_paid=balance, recorded_by=recorded_by
            )
            summary["created"] += 1
    return summary
