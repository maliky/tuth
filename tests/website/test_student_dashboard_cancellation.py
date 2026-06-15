"""Tests for student registration cancellation safeguards."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from app.finance.models.fee_stack import FeeStack, FeeStackLine
from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    FeeType,
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import (
    set_primary_std_curri_enroll,
)
from app.registry.models.registration import Registration, RegistrationStatus
from app.timetable.models.section import Section

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


def _std_regio_with_invoice(
    *,
    curriculum_course_factory,
    sem_factory,
    user_factory,
    student_username: str,
):
    """Build one student/registration/course-invoice tuple for cancellation tests."""
    RegistrationStatus._populate_attributes_and_db()
    RegistrationStatus.objects.get_or_create(
        code="canceled",
        defaults={"label": "Canceled"},
    )
    curriculum_course = curriculum_course_factory("931", "CURR_CANCEL")
    semester = sem_factory(1, datetime(2026, 1, 1))
    user = user_factory(student_username)
    student = Student(
        user=user,
        last_enrolled_semester=semester,
    )
    student.save()
    set_primary_std_curri_enroll(student, curriculum_course.curriculum)
    section = Section.objects.create(
        semester=semester,
        curriculum_course=curriculum_course,
        number=1,
    )
    registration = Registration.objects.create(
        student=student,
        section=section,
        status=RegistrationStatus.pending(),
    )
    tuition = curriculum_course.tuition_for()
    invoice = CrsInvoice.objects.create(
        curriculum_course=curriculum_course,
        student=student,
        semester=semester,
        initial_amount_due=tuition,
        balance=tuition,
    )
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None
    return user, student, registration, invoice, parent_invoice


def test_cancel_keeps_parent_invoice_when_sem_fees_exist(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Cancellation should keep parent invoice when semester fee stacks are attached."""
    user, _student, registration, invoice, parent_invoice = _std_regio_with_invoice(
        curriculum_course_factory=curriculum_course_factory,
        sem_factory=sem_factory,
        user_factory=user_factory,
        student_username="cancel_with_fees",
    )
    fee_stack = FeeStack.objects.create(name="Registration Semester Fee")
    FeeStackLine.objects.create(
        fee_stack=fee_stack,
        fee_type=_fee_type("registration", "Registration"),
        amount=Decimal("15.00"),
        effective_from_semester=None,
    )
    parent_invoice.fee_stacks.add(fee_stack)

    client.force_login(user)
    response = client.post(
        reverse("student_dashboard"),
        {"action": "cancel_registration", "registration_id": registration.id},
    )
    assert response.status_code == 302

    registration.refresh_from_db()
    assert registration.status_id == "canceled"
    assert not CrsInvoice.objects.filter(pk=invoice.pk).exists()
    assert StdSemesterInvoice.objects.filter(pk=parent_invoice.pk).exists()


def test_cancel_keeps_parent_invoice_when_cleared_history_exists(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Cancellation should keep parent invoice when payment history has a cleared state."""
    user, _student, registration, invoice, parent_invoice = _std_regio_with_invoice(
        curriculum_course_factory=curriculum_course_factory,
        sem_factory=sem_factory,
        user_factory=user_factory,
        student_username="cancel_with_history",
    )

    payment = Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("5.00"),
        status_id="pending",
    )
    payment.status_id = "cleared"
    payment.save(update_fields=["status"])
    payment.status_id = "pending"
    payment.save(update_fields=["status"])

    client.force_login(user)
    response = client.post(
        reverse("student_dashboard"),
        {"action": "cancel_registration", "registration_id": registration.id},
    )
    assert response.status_code == 302

    registration.refresh_from_db()
    assert registration.status_id == "canceled"
    assert not CrsInvoice.objects.filter(pk=invoice.pk).exists()
    assert StdSemesterInvoice.objects.filter(pk=parent_invoice.pk).exists()


def test_student_dashboard_shows_fee_total_before_cleared_payments(
    client,
    curriculum_course_factory,
    sem_factory,
    user_factory,
) -> None:
    """Student dashboard should distinguish total fees from open balance."""
    user, _student, _registration, invoice, parent_invoice = _std_regio_with_invoice(
        curriculum_course_factory=curriculum_course_factory,
        sem_factory=sem_factory,
        user_factory=user_factory,
        student_username="dashboard_fee_total",
    )
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("5.00"),
        status_id="cleared",
    )

    client.force_login(user)
    response = client.get(reverse("student_dashboard"))

    parent_invoice.refresh_from_db()
    assert response.status_code == 200
    assert (
        f"Fees charged: USD {invoice.initial_amount_due:.2f}".encode() in response.content
    )
    assert b"Applied clearance: USD 5.00" in response.content
    assert f"USD {parent_invoice.balance:.2f}".encode() in response.content
