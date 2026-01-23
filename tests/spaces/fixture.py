"""Test fixtures of spaces."""

from __future__ import annotations
from typing import Callable, TypeAlias

import pytest

from app.spaces.models.core import Room, Space

RoomFactoryT: TypeAlias = Callable[[str, str], Room]
SpaceFactoryT: TypeAlias = Callable[[str], Space]


@pytest.fixture
def space() -> Space:
    return Space.get_default()


@pytest.fixture
def room() -> Room:
    return Room.get_default()


# ~~~~~~~~~~~~~~~~ Factory ~~~~~~~~~~~~~~~~
@pytest.fixture
def space_factory() -> SpaceFactoryT:
    def _make(code: str = "TBA"):
        return Space.objects.create(code=code)

    return _make


@pytest.fixture
def room_factory(space_factory) -> RoomFactoryT:
    def _make(room_code: str, space_code: str = "TBA"):
        space = space_factory(space_code)
        return Room.objects.create(code=room_code, space=space)

    return _make
