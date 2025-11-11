"""Test donor people module."""
import pytest

from app.people.models.donor import Donor


@pytest.mark.django_db
def test_donor_profile_creation(donor_factory):
    donor = donor_factory("donor")
    user = donor.user

    assert donor.donor_id == f"{Donor.ID_PREFIX}00001"
    assert user.groups.filter(name=Donor.GROUP).exists()
