"""Verify Room / Space unique-constraint and default-room logic."""

import pytest
from django.db import transaction, IntegrityError

from app.spaces.models.core import Space, Room

pytestmark = pytest.mark.django_db  # to avoid decorator on all tests


def test_unique_room_per_space():
    """Two rooms with the same code in the same space must raise IntegrityError."""
    space = Space.objects.create(code="BLDG", full_name="Building")
    Room.objects.create(code="101", space=space)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Room.objects.create(code="101", space=space)


@pytest.mark.django_db(transaction=True)  # needed for the transaction=True
def test_default_room_conflict():
    """When code and space are blank the save() hook defaults to (space='TBA', code='TBA').

    Saving a second empty room violates the composite unique key.
    """
    space = Space.get_default()
    Room(code="1", space=space).save()  # first implicit “TBA / TBA”
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Room(code="1", space=space).save()  # second conflicts with the first
