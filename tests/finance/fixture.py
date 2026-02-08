"""Finance test fixtures."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest

from app.finance.models.invoice import CourseInvoice
from app.registry.models.registration import Registration
from tests.constants import D100

InvoiceFactoryT: TypeAlias = Callable[[Registration, Decimal], CourseInvoice]


@pytest.fixture
def invoice_factory() -> InvoiceFactoryT:
    """Return a callable to build invoices for a registration."""

    def _make(registration: Registration, amount: Decimal = D100) -> CourseInvoice:
        return CourseInvoice.objects.create(
            curriculum_course=registration.section.curriculum_course,
            student=registration.student,
            semester=registration.section.semester,
            initial_amount_due=amount,
            balance=amount,
        )

    return _make
