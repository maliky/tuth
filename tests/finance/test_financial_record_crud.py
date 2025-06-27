import pytest
from decimal import Decimal
from app.finance.models import FinancialRecord


@pytest.mark.django_db
def test_financial_record_crud(student, staff):
    """CRUD operations for FinancialRecord."""
    record = FinancialRecord.objects.create(student=student, total_due=Decimal("100.00"), verified_by=staff)
    assert FinancialRecord.objects.filter(pk=record.pk).exists()

    fetched = FinancialRecord.objects.get(pk=record.pk)
    assert fetched == record

    fetched.total_due = Decimal("50.00")
    fetched.save()
    updated = FinancialRecord.objects.get(pk=record.pk)
    assert updated.total_due == Decimal("50.00")

    updated.delete()
    assert not FinancialRecord.objects.filter(pk=record.pk).exists()
