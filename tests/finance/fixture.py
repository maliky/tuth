"""Test fixtures of the finance app.

Factories return callables for creating additional objects on demand.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, TypeAlias

import pytest

from app.finance.choices import PaymentMethod
from app.finance.models import (
    FinancialRecord,
    Payment,
    PaymentHistory,
    Scholarship,
)
from app.people.models.donor import Donor
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.academics.models.program import Program
from tests.academics.fixture import ProgramFactory
from tests.people.fixture import StaffFactory

FinancialRecordFactory: TypeAlias = Callable[[Student, Decimal], FinancialRecord]
PaymentFactory: TypeAlias = Callable[[Program, Staff, Decimal], Payment]
PaymentHistoryFactory: TypeAlias = Callable[
    [FinancialRecord, Staff, Decimal], PaymentHistory
]
ScholarshipFactory: TypeAlias = Callable[[Donor, Student, Decimal], Scholarship]

DECIMAL_0 = Decimal("0")
DECIMAL_1 = Decimal("1")
TODAY = date.today()


@pytest.fixture
def financial_record(student) -> FinancialRecord:
    """Default financial record for a student."""

    return FinancialRecord.objects.create(student=student, total_due=DECIMAL_0)


@pytest.fixture
def payment(financial_record, staff, program) -> Payment:
    """Default payment record for a program."""

    return Payment.objects.create(
        program=program, amount=DECIMAL_1, method=PaymentMethod.CASH, recorded_by=staff
    )


@pytest.fixture
def payment_history(financial_record, staff) -> PaymentHistory:
    """Default payment history entry."""

    return PaymentHistory.objects.create(
        financial_record=financial_record, amount=DECIMAL_1, recorded_by=staff
    )


@pytest.fixture
def scholarship(donor_factory, student_factor) -> Scholarship:
    """Default scholarship linking donor and student."""
    donor = donor_factory()
    student = student_factory()
    return Scholarship.objects.create(
        donor=donor, student=student, amount=DECIMAL_1, start_date=TODAY
    )


# ~~~~~~~~~~~~~~~~ Factories ~~~~~~~~~~~~~~~~


@pytest.fixture
def financial_record_factory(student_factory) -> FinancialRecordFactory:
    """Return a callable to build financial records."""

    def _make(student, total_due: Decimal = DECIMAL_0) -> FinancialRecord:
        return FinancialRecord.objects.create(student=student, total_due=total_due)

    return _make


@pytest.fixture
def payment_factory(program_factory:ProgramFactory, staff_factory:StaffFactory) -> PaymentFactory:
    """Return a callable to build payment records."""

    def _make(program, staff, amount: Decimal = DECIMAL_1) -> Payment:
        return Payment.objects.create(
            program=program, amount=amount, method=PaymentMethod.CASH, recorded_by=staff
        )

    return _make


@pytest.fixture
def payment_history_factory(financial_record_factory, staff_factory) -> PaymentHistoryFactory:
    """Return a callable to build payment history entries."""

    def _make(
        financial_record, staff, amount: Decimal = DECIMAL_1
    ) -> PaymentHistory:
        return PaymentHistory.objects.create(
            financial_record=financial_record, amount=amount, recorded_by=staff
        )

    return _make


@pytest.fixture
def scholarship_factory() -> ScholarshipFactory:
    """Return a callable to build scholarships."""

    def _make(
        donor: Donor,
        student: Student,
        amount: Decimal = DECIMAL_1,
        start_date: date = TODAY,
    ) -> Scholarship:
        return Scholarship.objects.create(
            donor=donor, student=student, amount=amount, start_date=start_date
        )

    return _make
