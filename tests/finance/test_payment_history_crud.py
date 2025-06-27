import pytest
from decimal import Decimal
from app.finance.models import FinancialRecord, PaymentHistory


@pytest.mark.django_db
def test_payment_history_crud(student, staff):
    """CRUD operations for PaymentHistory."""
    record = FinancialRecord.objects.create(student=student, total_due=Decimal("0"))
    history = PaymentHistory.objects.create(
        financial_record=record,
        amount=Decimal("25.00"),
        recorded_by=staff,
    )
    assert PaymentHistory.objects.filter(pk=history.pk).exists()

    fetched = PaymentHistory.objects.get(pk=history.pk)
    assert fetched == history

    fetched.amount = Decimal("30.00")
    fetched.save()
    updated = PaymentHistory.objects.get(pk=history.pk)
    assert updated.amount == Decimal("30.00")

    updated.delete()
    assert not PaymentHistory.objects.filter(pk=history.pk).exists()
