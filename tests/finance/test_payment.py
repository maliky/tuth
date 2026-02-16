"""Tests for payment-driven parent-invoice balance behavior."""

import pytest
from decimal import Decimal

from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from tests.constants import D10, D100
from app.registry.models.status_types import RegistrationStatus

pytestmark = pytest.mark.django_db
pytest_plugins = ["tests.finance.fixture"]


@pytest.fixture(autouse=True)
def _ensure_finance_payment_dfts() -> None:
    """Create lookup rows required by payment and invoice foreign keys."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def test_pending_payments_are_informational(regio_factory, invoice_factory):
    """Pending payments should not lower the parent or child invoice balances."""
    reg = regio_factory("student_pending", "CURRI_TEST", "101", 1)
    invoice = invoice_factory(reg, D100)
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None

    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=D10,
        status_id="pending",
    )

    invoice.refresh_from_db()
    parent_invoice.refresh_from_db()
    reg.refresh_from_db()
    assert parent_invoice.balance == D100
    assert invoice.balance == D100
    assert reg.status == RegistrationStatus.pending()


def test_cleared_payments_reduce_balances_and_update_regio(
    regio_factory,
    invoice_factory,
):
    """Cleared payments should drive invoice balances and registration status."""

    reg = regio_factory("student_cleared", "CURRI_TEST", "101", 1)

    invoice = invoice_factory(reg, D100)
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None

    assert reg.status == RegistrationStatus.pending()

    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("40.00"),
        status_id="cleared",
    )
    parent_invoice.refresh_from_db()
    invoice.refresh_from_db()
    reg.refresh_from_db()
    assert parent_invoice.balance == Decimal("60.00")
    assert invoice.balance == Decimal("60.00")
    assert reg.status == RegistrationStatus.partialy_cleared()

    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("60.00"),
        status_id="cleared",
    )
    parent_invoice.refresh_from_db()
    invoice.refresh_from_db()
    reg.refresh_from_db()
    assert parent_invoice.balance == 0
    assert invoice.balance == 0
    assert reg.status == RegistrationStatus.cleared()
