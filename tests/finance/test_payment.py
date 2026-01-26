"""Tests for payment-driven registration status updates."""

from decimal import Decimal

import pytest

from app.finance.models.payment import Payment
from app.registry.models.status_types import RegistrationStatus

pytestmark = pytest.mark.django_db
pytest_plugins = ["tests.finance.fixture"]

D10 = Decimal("10.00")
D20 = Decimal("20.00")
D30 = Decimal("30.00")
D100 = Decimal("100.00")


def test_payment_registration_cycle(registration_factory, invoice_factory):
    """Payments should update registration status based on invoice balance."""

    reg = registration_factory("student_cycle", "CURRI_TEST", "101", 1)

    invoice = invoice_factory(reg, D100)

    assert reg.status == RegistrationStatus.pending()

    Payment.objects.create(invoice=invoice, amount_paid=D10)
    reg.refresh_from_db()
    assert reg.status == RegistrationStatus.pending()

    Payment.objects.create(invoice=invoice, amount_paid=D10)
    reg.refresh_from_db()
    assert reg.status == RegistrationStatus.pending()

    Payment.objects.create(invoice=invoice, amount_paid=D20)
    reg.refresh_from_db()
    assert reg.status == RegistrationStatus.partialy_cleared()

    Payment.objects.create(invoice=invoice, amount_paid=D10)
    reg.refresh_from_db()
    assert reg.status == RegistrationStatus.partialy_cleared()

    Payment.objects.create(invoice=invoice, amount_paid=D30)
    reg.refresh_from_db()
    assert reg.status == RegistrationStatus.partialy_cleared()

    Payment.objects.create(invoice=invoice, amount_paid=D30)
    reg.refresh_from_db()
    assert reg.status == RegistrationStatus.cleared()
