"""Tests for payment-driven registration status updates."""

import pytest

from app.finance.models.payment import Payment
from tests.constants import D10, D20, D30, D100
from app.registry.models.status_types import RegistrationStatus

pytestmark = pytest.mark.django_db
pytest_plugins = ["tests.finance.fixture"]


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
