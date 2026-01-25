"""Tests for payment-driven registration status updates."""

from decimal import Decimal

import pytest

from app.finance.models.invoice import Invoice
from app.finance.models.payment import ClearanceStatus, Payment
from app.registry.models.registration import Registration

pytestmark = pytest.mark.django_db


def _create_invoice(student, section, amount: Decimal) -> Invoice:
    """Create an invoice tied to the student's curriculum course and semester."""
    return Invoice.objects.create(
        curriculum_course=section.curriculum_course,
        student=student,
        semester=section.semester,
        balance=amount,
    )


def _ensure_cleared_status() -> ClearanceStatus:
    """Ensure the cleared payment status exists for test payments."""
    status, _ = ClearanceStatus.objects.get_or_create(
        code="cleared",
        defaults={"label": "Cleared"},
    )
    return status


def test_registration_approved_at_40_percent(student, section):
    """Payments at 40% should mark registrations approved, not cleared."""
    invoice = _create_invoice(student, section, Decimal("100.00"))
    registration = Registration.objects.create(student=student, section=section)
    cleared_status = _ensure_cleared_status()

    Payment.objects.create(
        invoice=invoice,
        amount_paid=Decimal("40.00"),
        status=cleared_status,
    )

    registration.refresh_from_db()
    assert registration.status_id == "approved"


def test_registration_pending_below_40_percent(student, section):
    """Payments below 40% should keep registrations pending."""
    invoice = _create_invoice(student, section, Decimal("100.00"))
    registration = Registration.objects.create(student=student, section=section)
    cleared_status = _ensure_cleared_status()

    Payment.objects.create(
        invoice=invoice,
        amount_paid=Decimal("39.00"),
        status=cleared_status,
    )

    registration.refresh_from_db()
    assert registration.status_id == "pending"


def test_registration_cleared_when_fully_paid(student, section):
    """Fully paid invoices should mark registrations financially cleared."""
    invoice = _create_invoice(student, section, Decimal("100.00"))
    registration = Registration.objects.create(student=student, section=section)
    cleared_status = _ensure_cleared_status()

    Payment.objects.create(
        invoice=invoice,
        amount_paid=Decimal("40.00"),
        status=cleared_status,
    )
    Payment.objects.create(
        invoice=invoice,
        amount_paid=Decimal("60.00"),
        status=cleared_status,
    )

    registration.refresh_from_db()
    assert registration.status_id == "cleared"
