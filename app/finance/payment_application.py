"""Helpers for displaying how payment records apply to semester invoices."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, TypeAlias, TypedDict

from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.payment import Payment

PaymentRowsT: TypeAlias = Iterable[Payment]

ZERO_MONEY = Decimal("0.00")


class InvoicePaymentApplicationT(TypedDict):
    """Display totals separating raw records from applied clearance."""

    charged_total: Decimal
    open_balance: Decimal
    cleared_records_total: Decimal
    pending_records_total: Decimal
    pending_count: int
    applied_clearance: Decimal
    surplus: Decimal


def _money(value: Decimal | None) -> Decimal:
    """Return a non-null monetary value."""
    return value if value is not None else ZERO_MONEY


def _positive(value: Decimal) -> Decimal:
    """Clamp a monetary value at zero for display-only balances."""
    return value if value > ZERO_MONEY else ZERO_MONEY


def payment_application_for_parent_invoice(
    parent_invoice: StdSemesterInvoice,
    payments: PaymentRowsT | None = None,
) -> InvoicePaymentApplicationT:
    """Return how payment/waiver records apply to one semester invoice."""
    payment_rows = (
        list(payments) if payments is not None else list(parent_invoice.payments.all())
    )
    cleared_total = sum(
        (
            _money(payment.amount_paid)
            for payment in payment_rows
            if payment.status_id == "cleared"
        ),
        ZERO_MONEY,
    )
    pending_rows = [payment for payment in payment_rows if payment.status_id == "pending"]
    pending_total = sum(
        (_money(payment.amount_paid) for payment in pending_rows),
        ZERO_MONEY,
    )
    charged_total = _money(parent_invoice.initial_amount_due)
    applied_clearance = min(charged_total, cleared_total)
    return {
        "charged_total": charged_total,
        "open_balance": _money(parent_invoice.get_balance()),
        "cleared_records_total": cleared_total,
        "pending_records_total": pending_total,
        "pending_count": len(pending_rows),
        "applied_clearance": applied_clearance,
        "surplus": _positive(cleared_total - charged_total),
    }


__all__ = [
    "InvoicePaymentApplicationT",
    "payment_application_for_parent_invoice",
]
