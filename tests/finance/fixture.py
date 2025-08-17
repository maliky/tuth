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
from tests.academics.fixture import ProgramFactory
from tests.people.fixture import StaffFactory

FinancialRecordFactory: TypeAlias = Callable[[str, str, Decimal], FinancialRecord]
PaymentFactory: TypeAlias = Callable[[str, str, str, Decimal], Payment]
PaymentHistoryFactory: TypeAlias = Callable[
    [str, str, str, Decimal, Decimal], PaymentHistory
]
ScholarshipFactory: TypeAlias = Callable[[str, str, str, Decimal, date], Scholarship]

DECIMAL_0 = Decimal("0")
DECIMAL_1 = Decimal("1")
DECIMAL_10 = Decimal("10")
TODAY = date.today()


@pytest.fixture
def financial_record(student) -> FinancialRecord:
    """Default financial record for a student."""

    return FinancialRecord.objects.create(student=student, amount_due=DECIMAL_10)


@pytest.fixture
def payment(financial_record, staff, program) -> Payment:
    """Default payment record for a program."""
    return Payment.objects.create(
        program=program,
        amount=DECIMAL_1,
        method=PaymentMethod.get_default(),
        recorded_by=staff,
    )


@pytest.fixture
def payment_history(financial_record, staff) -> PaymentHistory:
    """Default payment history entry."""

    return PaymentHistory.objects.create(
        financial_record=financial_record, amount=DECIMAL_1, recorded_by=staff
    )


@pytest.fixture
def scholarship(donor, student) -> Scholarship:
    """Default scholarship linking donor and student."""
    return Scholarship.objects.create(
        donor=donor, student=student, amount=DECIMAL_1, start_date=TODAY
    )


# ~~~~~~~~~~~~~~~~ Factories ~~~~~~~~~~~~~~~~


@pytest.fixture
def financial_record_factory(student_factory) -> FinancialRecordFactory:
    """Return a callable to build financial records."""

    def _make(
        student_uname: str, curri_short_name: str, amount_due: Decimal = DECIMAL_0
    ) -> FinancialRecord:
        return FinancialRecord.objects.create(
            student=student_factory(student_uname, curri_short_name),
            amount_due=amount_due,
        )

    return _make


@pytest.fixture
def payment_factory(
    program_factory: ProgramFactory, staff_factory: StaffFactory
) -> PaymentFactory:
    """Return a callable to build payment records."""

    def _make(
        course_no: str,
        curri_short_name: str,
        staff_uname: str,
        amount: Decimal = DECIMAL_1,
    ) -> Payment:
        return Payment.objects.create(
            program=program_factory(course_no, curri_short_name),
            amount=amount,
            method=PaymentMethod.get_default(),
            recorded_by=staff_factory(staff_uname),
        )

    return _make


@pytest.fixture
def payment_history_factory(
    financial_record_factory, staff_factory
) -> PaymentHistoryFactory:
    """Return a callable to build payment history entries."""

    def _make(
        stud_uname: str,
        curri_short_name: str,
        staff_uname: str,
        amount_paid: Decimal = DECIMAL_1,
        amount_due: Decimal = DECIMAL_10,
    ) -> PaymentHistory:
        staff = staff_factory(staff_uname)
        financial_record = financial_record_factory(
            stud_uname, curri_short_name, amount_due=amount_due
        )

        return PaymentHistory.objects.create(
            financial_record=financial_record, amount=amount_paid, recorded_by=staff
        )

    return _make


@pytest.fixture
def scholarship_factory(donor_factory, student_factory) -> ScholarshipFactory:
    """Return a callable to build scholarships."""

    def _make(
        donor_uname: str,
        student_uname: str,
        curri_short_name: str = "DFT_CURRI",
        amount: Decimal = DECIMAL_1,
        start_date: date = TODAY,
    ) -> Scholarship:
        return Scholarship.objects.create(
            donor=donor_factory(donor_uname),
            student=student_factory(student_uname, curri_short_name),
            amount=amount,
            start_date=start_date,
        )

    return _make
