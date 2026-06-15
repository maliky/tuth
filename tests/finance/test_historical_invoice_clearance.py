"""Tests for historical finance clearance reconciliation."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from app.academics.models.curriculum_course import CurriCrs
from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.student import Student
from app.timetable.models.semester import Semester

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _ensure_finance_defaults() -> None:
    """Create finance lookup rows needed by invoices and payments."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _student(username: str, semester: Semester) -> Student:
    """Create a disposable student for historical reconciliation tests."""
    user = User.objects.create_user(
        username=username,
        first_name=username.title(),
        last_name="Student",
    )
    student = Student(user=user, last_enrolled_semester=semester)
    student.save()
    return student


def _open_invoice(
    *,
    student: Student,
    curriculum_course: CurriCrs,
    semester: Semester,
    amount: Decimal,
) -> tuple[CrsInvoice, StdSemesterInvoice]:
    """Create one open course invoice and return it with its parent invoice."""
    invoice = CrsInvoice.objects.create(
        student=student,
        curriculum_course=curriculum_course,
        semester=semester,
        initial_amount_due=amount,
        balance=amount,
    )
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None
    parent_invoice.refresh_from_db()
    invoice.refresh_from_db()
    return invoice, parent_invoice


def _audit_rows(path: Path) -> list[dict[str, str]]:
    """Read reconciliation audit CSV rows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_historical_clearance_dry_run_does_not_mutate(
    curriculum_course_factory,
    sem_factory,
    tmp_path,
) -> None:
    """Dry-run should report historical targets without writing payments."""
    historical_semester = sem_factory(2, datetime(2025, 8, 1))
    cutoff_semester = sem_factory(3, datetime(2025, 8, 1))
    student = _student("hist_dry_run", cutoff_semester)
    historical_course = curriculum_course_factory("901", "CURR_HIST_CLEAR")
    current_course = curriculum_course_factory("902", "CURR_HIST_CLEAR")
    _open_invoice(
        student=student,
        curriculum_course=historical_course,
        semester=historical_semester,
        amount=Decimal("90.00"),
    )
    _open_invoice(
        student=student,
        curriculum_course=current_course,
        semester=cutoff_semester,
        amount=Decimal("120.00"),
    )
    audit_path = tmp_path / "dry_run.csv"

    call_command(
        "reconcile_historical_invoice_clearance",
        cutoff_semester="25-26-S3",
        log_path=str(audit_path),
    )

    assert Payment.objects.count() == 0
    rows = _audit_rows(audit_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "would_clear"
    assert rows[0]["action"] == "would_create_payment"


def test_historical_clearance_updates_one_pending_payment_and_skips_current(
    curriculum_course_factory,
    sem_factory,
    tmp_path,
) -> None:
    """Apply mode clears historical invoices but leaves the cutoff semester open."""
    historical_semester = sem_factory(2, datetime(2025, 8, 1))
    cutoff_semester = sem_factory(3, datetime(2025, 8, 1))
    student = _student("hist_apply", cutoff_semester)
    historical_course = curriculum_course_factory("903", "CURR_HIST_CLEAR")
    current_course = curriculum_course_factory("904", "CURR_HIST_CLEAR")
    historical_invoice, historical_parent = _open_invoice(
        student=student,
        curriculum_course=historical_course,
        semester=historical_semester,
        amount=Decimal("90.00"),
    )
    current_invoice, current_parent = _open_invoice(
        student=student,
        curriculum_course=current_course,
        semester=cutoff_semester,
        amount=Decimal("120.00"),
    )
    payment = Payment.objects.create(
        student_semester_invoice=historical_parent,
        amount_paid=Decimal("1.00"),
        status_id="pending",
    )
    audit_path = tmp_path / "apply.csv"

    call_command(
        "reconcile_historical_invoice_clearance",
        cutoff_semester="25-26-S3",
        log_path=str(audit_path),
        apply=True,
    )

    payment.refresh_from_db()
    historical_parent.refresh_from_db()
    historical_invoice.refresh_from_db()
    current_parent.refresh_from_db()
    current_invoice.refresh_from_db()
    assert payment.amount_paid == Decimal("90.00")
    assert payment.status_id == "cleared"
    assert historical_parent.balance == Decimal("0.00")
    assert historical_invoice.balance == Decimal("0.00")
    assert current_parent.balance == Decimal("120.00")
    assert current_invoice.balance == Decimal("120.00")
    assert _audit_rows(audit_path)[0]["action"] == "update_pending"


def test_historical_clearance_requires_manual_review_for_multiple_pending(
    curriculum_course_factory,
    sem_factory,
    tmp_path,
) -> None:
    """Multiple pending rows must not be guessed or auto-merged."""
    historical_semester = sem_factory(2, datetime(2025, 8, 1))
    cutoff_semester = sem_factory(3, datetime(2025, 8, 1))
    student = _student("hist_conflict", cutoff_semester)
    historical_course = curriculum_course_factory("905", "CURR_HIST_CLEAR")
    invoice, parent_invoice = _open_invoice(
        student=student,
        curriculum_course=historical_course,
        semester=historical_semester,
        amount=Decimal("90.00"),
    )
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("20.00"),
        status_id="pending",
    )
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("70.00"),
        status_id="pending",
    )
    audit_path = tmp_path / "conflict.csv"

    call_command(
        "reconcile_historical_invoice_clearance",
        cutoff_semester="25-26-S3",
        log_path=str(audit_path),
        apply=True,
    )

    parent_invoice.refresh_from_db()
    invoice.refresh_from_db()
    assert parent_invoice.balance == Decimal("90.00")
    assert invoice.balance == Decimal("90.00")
    assert Payment.objects.filter(status_id="pending").count() == 2
    rows = _audit_rows(audit_path)
    assert rows[0]["status"] == "conflict"
    assert rows[0]["action"] == "skip_multiple_pending"
