import pytest
from decimal import Decimal
from app.finance.models import SectionFee


@pytest.mark.django_db
def test_sectionfee_crud(section_factory):
    """CRUD operations for SectionFee."""
    section = section_factory(1)
    fee = SectionFee.objects.create(
        section=section,
        fee_type="lab",
        amount=Decimal("25.00"),
    )
    assert SectionFee.objects.filter(pk=fee.pk).exists()

    fetched = SectionFee.objects.get(pk=fee.pk)
    assert fetched == fee

    fetched.amount = Decimal("50.00")
    fetched.save()
    updated = SectionFee.objects.get(pk=fee.pk)
    assert updated.amount == Decimal("50.00")

    updated.delete()
    assert not SectionFee.objects.filter(pk=fee.pk).exists()
