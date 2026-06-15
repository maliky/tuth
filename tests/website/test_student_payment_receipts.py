"""Student payment receipt display regressions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _ensure_payment_receipt_dfts() -> None:
    """Create finance lookup rows required by receipt tests."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def test_student_receipt_shows_surplus_apart_from_applied_clearance(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Receipt totals should cap applied clearance at semester charges."""
    curriculum_course = curriculum_course_factory("921", "CURRI_RECEIPT")
    semester = sem_factory(1, datetime(2026, 1, 1))
    user = user_factory("receipt_surplus_student")
    student = Student(user=user, last_enrolled_semester=semester)
    student.save()
    set_primary_std_curri_enroll(student, curriculum_course.curriculum)
    invoice = CrsInvoice.objects.create(
        student=student,
        curriculum_course=curriculum_course,
        semester=semester,
        initial_amount_due=Decimal("45.00"),
        balance=Decimal("45.00"),
    )
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("100.00"),
        status_id="cleared",
    )

    client.force_login(user)
    response = client.get(reverse("std_payment_receipt", args=[semester.id]))

    assert response.status_code == 200
    assert b"Applied clearance" in response.content
    assert b"USD 45.00" in response.content
    assert b"Payment/waiver records: USD 100.00" in response.content
    assert b"Surplus to review: USD 55.00" in response.content
