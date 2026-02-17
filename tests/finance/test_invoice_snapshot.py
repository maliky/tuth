"""Tests for parent-first invoice snapshot totals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.finance.models.fee_stack import FeeStack, FeeStackLine
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    FeeType,
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.finance.utils import build_invoice_snapshot

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _ensure_finance_payment_dfts() -> None:
    """Create lookup rows required by parent invoice and payment foreign keys."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_build_invoice_snapshot_uses_parent_totals(
    curriculum_course_factory,
    sem_factory,
    student,
) -> None:
    """Snapshot totals should come from parent semester invoice aggregation."""
    curriculum_course = curriculum_course_factory("891", "CURR_SSI_SNAPSHOT")
    semester = sem_factory(1, datetime(2026, 1, 1))
    student.curriculum = curriculum_course.curriculum
    student.last_enrolled_semester = semester
    student.save(update_fields=["curriculum", "last_enrolled_semester"])

    tuition = curriculum_course.tuition_for()
    course_invoice = CrsInvoice.objects.create(
        curriculum_course=curriculum_course,
        student=student,
        semester=semester,
        initial_amount_due=tuition,
        balance=tuition,
    )
    parent_invoice = course_invoice.student_semester_invoice
    assert parent_invoice is not None

    semester_stack = FeeStack.objects.create(name="Semester Registration Fee")
    FeeStackLine.objects.create(
        fee_stack=semester_stack,
        fee_type=_fee_type("registration", "Registration"),
        amount=Decimal("25.00"),
        effective_from_semester=None,
    )
    parent_invoice.fee_stacks.add(semester_stack)
    parent_invoice.refresh_from_db()
    assert parent_invoice.initial_amount_due == tuition + Decimal("25.00")

    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("20.00"),
        status_id="cleared",
    )
    parent_invoice.refresh_from_db()

    snapshot = build_invoice_snapshot(
        [course_invoice],
        student=student,
        semester=semester,
    )
    payload = snapshot.payload

    assert snapshot.total_amount == parent_invoice.initial_amount_due
    assert payload["total_bill"] == f"{parent_invoice.initial_amount_due:.2f}"
    assert payload["payments"] == "20.00"
    assert payload["balance"] == f"{parent_invoice.balance:.2f}"
    assert payload["required_deposit"] == f"{parent_invoice.required_deposit_amount:.2f}"
    assert any(
        fee_line["label"] == semester_stack.name for fee_line in payload["fee_lines"]
    )
