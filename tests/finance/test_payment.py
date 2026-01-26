"""Tests for payment-driven registration status updates."""

from decimal import Decimal

import pytest

from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import PaymentStatus
from app.registry.models.status_types import RegistrationStatus

pytestmark = pytest.mark.django_db
pytest_plugins = ["tests.finance.fixture"]

D10 = Decimal("10.00")
D20 = Decimal("20.00")
# D30 = Decimal("30.00")
D40 = Decimal("40.00")
D100 = Decimal("100.00")


def test_payment_registration_cycle(registration_factory, invoice_factory):
    """Payments should update registration status based on invoice balance."""

    reg = registration_factory("student_cycle", "CURRI_TEST", "101", 1)

    invoice = invoice_factory(reg, D100)

    cleared = PaymentStatus.get_by_code("cleared")

    assert reg.status_id == RegistrationStatus.pending().id

    Payment.objects.create(invoice=invoice, amount_paid=D10, status=cleared)
    reg.refresh_from_db()
    assert reg.status_id == RegistrationStatus.pending().id

    Payment.objects.create(invoice=invoice, amount_paid=D10, status=cleared)
    reg.refresh_from_db()
    assert reg.status_id == RegistrationStatus.partialy_cleared().id

    Payment.objects.create(invoice=invoice, amount_paid=D40, status=cleared)
    reg.refresh_from_db()
    assert reg.status_id == RegistrationStatus.partialy_cleared().id

    Payment.objects.create(invoice=invoice, amount_paid=D10, status=cleared)
    reg.refresh_from_db()
    assert reg.status_id == RegistrationStatus.partialy_cleared().id

    Payment.objects.create(invoice=invoice, amount_paid=D20, status=cleared)
    reg.refresh_from_db()
    assert reg.status_id == RegistrationStatus.cleared().id

    Payment.objects.create(invoice=invoice, amount_paid=D10, status=cleared)
    reg.refresh_from_db()
    assert reg.status_id == RegistrationStatus.partialy_cleared().id
