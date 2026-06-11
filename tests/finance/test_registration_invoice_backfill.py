"""Tests for registration-driven invoice materialization."""

from __future__ import annotations

from decimal import Decimal

from django.core.management import call_command

import pytest

from app.finance.models.invoice import CrsInvoice
from app.finance.registration_invoices import ensure_course_invoice_for_registration
from app.registry.models.credit_hours import CreditHour

pytestmark = pytest.mark.django_db


def test_registration_invoice_helper_creates_course_invoice(regio_factory) -> None:
    """A pending registration without finance rows should become actionable."""
    registration = regio_factory("invoice_helper_student", "CURRI_INV_HELP", "801", 1)
    amount_due = registration.section.fee_total_amount()

    invoice, created, updated = ensure_course_invoice_for_registration(registration)

    assert invoice is not None
    assert created is True
    assert updated is False
    assert invoice.initial_amount_due == amount_due
    assert invoice.balance == amount_due
    assert invoice.student_semester_invoice is not None
    invoice.student_semester_invoice.refresh_from_db()
    assert invoice.student_semester_invoice.balance == amount_due

    second_invoice, second_created, second_updated = (
        ensure_course_invoice_for_registration(registration)
    )
    assert second_invoice == invoice
    assert second_created is False
    assert second_updated is False


def test_backfill_registration_invoices_command_supports_dry_run(regio_factory) -> None:
    """Backfill command should report safely before writing invoices."""
    registration = regio_factory("invoice_command_student", "CURRI_INV_CMD", "802", 1)

    call_command(
        "backfill_registration_invoices",
        student=registration.student.username,
        dry_run=True,
    )
    assert CrsInvoice.objects.count() == 0

    call_command(
        "backfill_registration_invoices",
        student=registration.student.username,
    )
    assert CrsInvoice.objects.filter(student=registration.student).count() == 1


def test_registration_invoice_helper_updates_stale_zero_invoice(regio_factory) -> None:
    """The billing minimum should let an existing zero invoice become billable."""
    registration = regio_factory("invoice_zero_student", "CURRI_INV_ZERO", "806", 1)
    curriculum_course = registration.section.curriculum_course
    curriculum_course.credit_hours = CreditHour.objects.get(code=0)
    curriculum_course.save(update_fields=["credit_hours"])
    stale_invoice = CrsInvoice.objects.create(
        student=registration.student,
        curriculum_course=curriculum_course,
        semester=registration.section.semester,
        initial_amount_due=Decimal("0.00"),
        balance=Decimal("0.00"),
    )

    invoice, created, updated = ensure_course_invoice_for_registration(registration)

    assert invoice == stale_invoice
    assert created is False
    assert updated is True
    invoice.refresh_from_db()
    assert invoice.initial_amount_due == Decimal("15.00")
    assert invoice.balance == Decimal("15.00")


def test_backfill_registration_invoices_command_patches_existing_zero_invoice(
    regio_factory,
) -> None:
    """Backfill should patch stale zero invoices when include-existing is set."""
    registration = regio_factory("invoice_patch_student", "CURRI_INV_PATCH", "807", 1)
    curriculum_course = registration.section.curriculum_course
    curriculum_course.credit_hours = CreditHour.objects.get(code=0)
    curriculum_course.save(update_fields=["credit_hours"])
    CrsInvoice.objects.create(
        student=registration.student,
        curriculum_course=curriculum_course,
        semester=registration.section.semester,
        initial_amount_due=Decimal("0.00"),
        balance=Decimal("0.00"),
    )

    call_command(
        "backfill_registration_invoices",
        student=registration.student.username,
        include_existing=True,
    )

    invoice = CrsInvoice.objects.get(student=registration.student)
    assert invoice.initial_amount_due == Decimal("15.00")
    assert invoice.balance == Decimal("15.00")
