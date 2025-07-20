"""Test donor people module."""

import pytest
from django.contrib.auth import get_user_model

from app.people.models.donor import Donor


@pytest.mark.django_db
def test_donor_profile_creation():
    User = get_user_model()
    user = User.objects.create(username="donor")
    donor = Donor.objects.create(user=user)

    assert donor.donor_id == f"{Donor.ID_PREFIX}00001"
    assert user.groups.filter(name=Donor.GROUP).exists()
