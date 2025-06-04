"""Test room widget module."""

import pytest

from app.spaces.admin.widgets import RoomWidget
from app.spaces.models.building import Building
from app.spaces.models.room import Room


@pytest.mark.django_db
def test_room_widget_creates_building_and_room():
    rw = RoomWidget(model=Room, field="name")

    room = rw.clean("B1-101")

    building = Building.objects.get(short_name="B1")
    assert room.building == building
    assert room.name == "101"


@pytest.mark.django_db
def test_room_widget_returns_existing_room():
    building = Building.objects.create(short_name="B1")
    existing = Room.objects.create(name="101", building=building)
    rw = RoomWidget(model=Room, field="name")

    room = rw.clean("B1-101")

    assert room == existing
    assert Building.objects.count() == 1
    assert Room.objects.count() == 1


@pytest.mark.django_db
def test_room_widget_only_creates_building():
    rw = RoomWidget(model=Room, field="name")

    result = rw.clean("B2")

    assert result is None
    assert Building.objects.filter(short_name="B2").exists()
    assert Room.objects.count() == 0
