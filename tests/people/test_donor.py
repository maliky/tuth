"""Test donor people module."""

import pytest


from app.people.models.donor import Donor
from app.people.utils import mk_username


@pytest.mark.django_db
def test_donor_creation_sets_id_and_gp() -> None:
    donor = Donor.objects.create(first_name="Dani", last_name="Cole")

    expected_username = mk_username("Dani", "Cole")
    assert donor.donor_id.startswith(Donor.ID_PREFIX)
    assert donor.user.username == expected_username
    assert donor.user.groups.filter(name=Donor.GROUP).exists()


@pytest.mark.django_db
def test_donor_profile_creation(donor_factory):
    username = "Donor"
    donor = donor_factory(username)
    user = donor.user

    assert user.username == username, f"{user} !={username}"
    assert donor.username == username, f"{donor} !={username}"
