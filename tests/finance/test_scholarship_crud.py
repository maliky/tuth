import pytest
from datetime import date
from decimal import Decimal
from app.finance.models import Scholarship


@pytest.mark.django_db
def test_scholarship_crud(donor, student):
    """CRUD operations for Scholarship."""
    scholarship = Scholarship.objects.create(
        donor=donor,
        student=student,
        amount=Decimal("100.00"),
        start_date=date.today(),
    )
    assert Scholarship.objects.filter(pk=scholarship.pk).exists()

    fetched = Scholarship.objects.get(pk=scholarship.pk)
    assert fetched == scholarship

    fetched.amount = Decimal("150.00")
    fetched.save()
    updated = Scholarship.objects.get(pk=scholarship.pk)
    assert updated.amount == Decimal("150.00")

    updated.delete()
    assert not Scholarship.objects.filter(pk=scholarship.pk).exists()
