import pytest
from decimal import Decimal
from app.finance.models import Payment
from app.finance.choices import PaymentMethod


@pytest.mark.django_db
def test_payment_crud(program, staff):
    """CRUD operations for Payment."""
    payment = Payment.objects.create(
        program=program,
        amount=Decimal("10.00"),
        method=PaymentMethod.CASH,
        recorded_by=staff,
    )
    assert Payment.objects.filter(pk=payment.pk).exists()

    fetched = Payment.objects.get(pk=payment.pk)
    assert fetched == payment

    fetched.amount = Decimal("5.00")
    fetched.save()
    updated = Payment.objects.get(pk=payment.pk)
    assert updated.amount == Decimal("5.00")

    updated.delete()
    assert not Payment.objects.filter(pk=payment.pk).exists()
