import pytest
from decimal import Decimal
from app.finance.models import FinancialRecord, PaymentHistory


@pytest.mark.django_db
def test_payment_history_str(student_profile, staff_profile):
    fr = FinancialRecord.objects.create(student=student_profile, total_due=Decimal("0"))
    ph = PaymentHistory.objects.create(
        financial_record=fr, amount=Decimal("25.00"), recorded_by=staff_profile
    )
    assert str(ph) == f"{ph.amount} on {ph.payment_date.date()}"
