"""Finance test fixtures."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias

import pytest

from app.finance.models.invoice import CrsInvoice
from app.registry.models.registration import Registration
from tests.constants import D100

RegistrationInvoiceFactoryT: TypeAlias = Callable[[Registration, Decimal], CrsInvoice]


@pytest.fixture
def registration_invoice_factory() -> RegistrationInvoiceFactoryT:
    """Return a callable to build invoices for a registration."""

    def _make(registration: Registration, amount: Decimal = D100) -> CrsInvoice:
        return CrsInvoice.objects.create(
            curriculum_course=registration.section.curriculum_course,
            student=registration.student,
            semester=registration.section.semester,
            initial_amount_due=amount,
            balance=amount,
        )

    return _make
