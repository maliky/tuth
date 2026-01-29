"""Shared finance fixtures for Selenium and BDD tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest

from app.academics.models.curriculum_course import CurriculumCourse
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.timetable.models.semester import Semester
from tests.constants import D25, D100

StudentInvoiceFactoryT: TypeAlias = Callable[
    [Student, Semester, Decimal, CurriculumCourse | None], Invoice
]
PaymentFactoryT: TypeAlias = Callable[[Invoice, Decimal], Payment]



@pytest.fixture
def student_invoice_factory() -> StudentInvoiceFactoryT:
    """Return a callable to create invoices for students in a semester."""

    def _make(
        student: Student,
        semester: Semester,
        amount: Decimal = D100,
        curriculum_course: CurriculumCourse | None = None,
    ) -> Invoice:
        course = curriculum_course or CurriculumCourse.get_default()
        return Invoice.objects.create(
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

    def _make(invoice: Invoice, amount: Decimal = D25) -> Payment:
        return Payment.objects.create(invoice=invoice, amount_paid=amount)

    return _make
