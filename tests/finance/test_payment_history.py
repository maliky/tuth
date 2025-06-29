"""tests function for payment history of the finance app."""

# Fixtures from tests.conftest are automatically available; no explicit
# pytest_plugins declaration is needed.


from decimal import Decimal

import pytest

from app.finance.models.financial_record import FinancialRecord
from app.finance.models.payment_history import PaymentHistory

# from tests.fixtures.people import staff_profile, student_profile


@pytest.mark.django_db
def test_payment_history_str(student, staff):
    fr = FinancialRecord.objects.create(student=student, total_due=Decimal("0"))
    ph = PaymentHistory.objects.create(
        financial_record=fr, amount=Decimal("25.00"), recorded_by=staff
    )
    assert (
        str(ph)
        == f"{ph.amount} on {ph.payment_date_str} for {ph.financial_record.student}"
    )


@pytest.mark.django_db
def test_payment_date_str_returns_non_empty_string(student, staff):
    """payment_date_str should always return a non-empty string."""
    fr = FinancialRecord.objects.create(student=student, total_due=Decimal("0"))
    ph = PaymentHistory.objects.create(
        financial_record=fr, amount=Decimal("25.00"), recorded_by=staff
    )
    assert isinstance(ph.payment_date_str, str)
    assert ph.payment_date_str != ""
