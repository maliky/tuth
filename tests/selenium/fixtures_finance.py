"""Shared finance fixtures for Selenium and BDD tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest

from app.academics.models.curriculum_course import CurriCrs
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.timetable.models.semester import Semester
from tests.constants import D25, D100

StdInvoiceFactoryT: TypeAlias = Callable[
    [Student, Semester, Decimal, CurriCrs | None], CrsInvoice
]
PaymentFactoryT: TypeAlias = Callable[[CrsInvoice, Decimal], Payment]


@pytest.fixture
def std_invoice_factory() -> StdInvoiceFactoryT:
    """Return a callable to create invoices for students in a semester."""

    def _make(
        student: Student,
        semester: Semester,
        amount: Decimal = D100,
        curriculum_course: CurriCrs | None = None,
    ) -> CrsInvoice:
        course = curriculum_course or CurriCrs.get_dft()
        return CrsInvoice.objects.create(
            curriculum_course=course,
            student=student,
            semester=semester,
            initial_amount_due=amount,
            balance=amount,
        )

    return _make


@pytest.fixture
def payment_factory() -> PaymentFactoryT:
    """Return a callable to create payments for an invoice."""

    def _make(invoice: CrsInvoice, amount: Decimal = D25) -> Payment:
        parent_invoice = invoice.student_semester_invoice
        assert parent_invoice is not None
        return Payment.objects.create(
            student_semester_invoice=parent_invoice,
            amount_paid=amount,
        )

    return _make
