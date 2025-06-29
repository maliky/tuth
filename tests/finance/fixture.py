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

FinancialRecordFactory: TypeAlias = Callable[[Student, Decimal], FinancialRecord]
PaymentFactory: TypeAlias = Callable[[Program, Staff, Decimal], Payment]
PaymentHistoryFactory: TypeAlias = Callable[[FinancialRecord, Staff, Decimal], PaymentHistory]
ScholarshipFactory: TypeAlias = Callable[[Donor, Student, Decimal], Scholarship]


@pytest.fixture
def financial_record(student: Student) -> FinancialRecord:
    """Default financial record for a student."""

    return FinancialRecord.objects.create(student=student, total_due=Decimal("0"))


@pytest.fixture
def payment(financial_record: FinancialRecord, staff: Staff, program: Program) -> Payment:
    """Default payment record for a program."""

    return Payment.objects.create(
        program=program,
        amount=Decimal("1"),
        method=PaymentMethod.CASH,
        recorded_by=staff,
    )


@pytest.fixture
def payment_history(financial_record: FinancialRecord, staff: Staff) -> PaymentHistory:
    """Default payment history entry."""

    return PaymentHistory.objects.create(
        financial_record=financial_record,
        amount=Decimal("1"),
        recorded_by=staff,
    )


@pytest.fixture
def scholarship(donor: Donor, student: Student) -> Scholarship:
    """Default scholarship linking donor and student."""

    return Scholarship.objects.create(
        donor=donor,
        student=student,
        amount=Decimal("1"),
        start_date=date.today(),
    )


# ─── factory fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def financial_record_factory() -> FinancialRecordFactory:
    """Return a callable to build financial records."""

    def _make(student: Student, total_due: Decimal = Decimal("0")) -> FinancialRecord:
        return FinancialRecord.objects.create(student=student, total_due=total_due)

    return _make


@pytest.fixture
def payment_factory() -> PaymentFactory:
    """Return a callable to build payment records."""

    def _make(
        program: Program,
        staff: Staff,
        amount: Decimal = Decimal("1"),
    ) -> Payment:
        return Payment.objects.create(
            program=program,
            amount=amount,
            method=PaymentMethod.CASH,
            recorded_by=staff,
        )

    return _make


@pytest.fixture
def payment_history_factory() -> PaymentHistoryFactory:
    """Return a callable to build payment history entries."""

    def _make(
        financial_record: FinancialRecord,
        staff: Staff,
        amount: Decimal = Decimal("1"),
    ) -> PaymentHistory:
        return PaymentHistory.objects.create(
            financial_record=financial_record,
            amount=amount,
            recorded_by=staff,
        )

    return _make


@pytest.fixture
def scholarship_factory() -> ScholarshipFactory:
    """Return a callable to build scholarships."""

    def _make(
        donor: Donor,
        student: Student,
        amount: Decimal = Decimal("1"),
        start_date: date = date.today(),
    ) -> Scholarship:
        return Scholarship.objects.create(
            donor=donor,
            student=student,
            amount=amount,
            start_date=start_date,
        )

    return _make

