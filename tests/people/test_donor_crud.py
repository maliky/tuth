import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from app.shared.status.mixins import StatusHistory
from app.people.models.donor import Donor


@pytest.mark.django_db
def test_donor_crud():
    """CRUD operations for Donor."""
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        pytest.skip("StatusHistory table not present in SQLite tests")
    User = get_user_model()
    user = User.objects.create(username="donor_crud")
    donor = Donor.objects.create(user=user)
    assert Donor.objects.filter(pk=donor.pk).exists()

    fetched = Donor.objects.get(pk=donor.pk)
    assert fetched == donor

    fetched.phone_number = "555"  # arbitrary field from AbstractPerson
    fetched.save()
    updated = Donor.objects.get(pk=donor.pk)
    assert updated.phone_number == "555"

    updated.delete()
    assert not Donor.objects.filter(pk=donor.pk).exists()
