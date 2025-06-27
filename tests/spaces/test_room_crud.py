import pytest
from app.spaces.models.core import Room, Space


@pytest.mark.django_db
def test_room_crud(space):
    """CRUD operations for Room."""
    room = Room.objects.create(code="101", space=space)
    assert Room.objects.filter(pk=room.pk).exists()

    fetched = Room.objects.get(pk=room.pk)
    assert fetched == room

    fetched.code = "102"
    fetched.save()
    updated = Room.objects.get(pk=room.pk)
    assert updated.code == "102"

    updated.delete()
    assert not Room.objects.filter(pk=room.pk).exists()
