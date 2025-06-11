"""Test room widget module."""

import pytest

from app.spaces.admin.widgets import RoomWidget
from app.spaces.models.core import Space, Room


@pytest.mark.django_db
def test_room_widget_creates_space_and_room():
    rw = RoomWidget(model=Room, field="name")

    room = rw.clean("B1-101")

    space = Space.objects.get(code="B1")
    assert room.location == space
    assert room.name == "101"


@pytest.mark.django_db
def test_room_widget_returns_existing_room():
    space = Space.objects.create(code="B1")
    existing = Room.objects.create(name="101", space=space)
    rw = RoomWidget(model=Room, field="name")

    room = rw.clean("B1-101")

    assert room == existing
    assert Space.objects.count() == 1
    assert Room.objects.count() == 1


@pytest.mark.django_db
def test_room_widget_only_creates_space():
    rw = RoomWidget(model=Room, field="name")

    result = rw.clean("B2")

    assert result is None
    assert Space.objects.filter(code="B2").exists()
    assert Room.objects.count() == 0
