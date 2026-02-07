"""Tests for invoice amount behavior with fee stack updates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.finance.models.fee_stack import CourseFeeStack, FeeStack, FeeStackLine
from app.finance.models.invoice import Invoice
from app.finance.models.status_types_methods import FeeType


pytestmark = pytest.mark.django_db


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_invoice_initial_amount_is_not_changed_by_later_fee_stack_update(
    section,
    student,
) -> None:
    """Invoice stores initial amount and does not retroactively follow fee edits."""
    student.curriculum = section.curriculum
    student.save(update_fields=["curriculum"])

    fee_stack = FeeStack.objects.create(name="Invoice Stack")
    fee_line = FeeStackLine.objects.create(
        fee_stack=fee_stack,
        fee_type=_fee_type("registration", "Registration"),
        amount=Decimal("10.00"),
    )
    CourseFeeStack.objects.create(course=section.course, fee_stack=fee_stack)

    initial_due = section.fee_total_amount()
    invoice = Invoice.objects.create(
        curriculum_course=section.curriculum_course,
        student=student,
        semester=section.semester,
        initial_amount_due=initial_due,
        balance=initial_due,
    )

    fee_line.amount = Decimal("18.00")
    fee_line.save(update_fields=["amount"])
    updated_due = section.fee_total_amount()

    assert updated_due > initial_due
    invoice.refresh_from_db()
    assert invoice.initial_amount_due == initial_due
    assert invoice.balance == initial_due
