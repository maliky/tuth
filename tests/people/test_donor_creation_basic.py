"""Concrete creation test for Donor."""

import pytest

from app.people.models.donor import Donor
from app.people.utils import mk_username


@pytest.mark.django_db
def test_donor_creation_sets_id_and_group() -> None:
    donor = Donor.objects.create(first_name="Dani", last_name="Cole")

    expected_username = mk_username("Dani", "Cole", prefix_len=2)
    assert donor.donor_id.startswith(Donor.ID_PREFIX)
    assert donor.user.username == expected_username
    assert donor.user.groups.filter(name=Donor.GROUP).exists()
