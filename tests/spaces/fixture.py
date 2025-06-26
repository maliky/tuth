"""Test fixtures of spaces."""

from __future__ import annotations

import pytest

from app.spaces.models.core import Room, Space


@pytest.fixture
def space() -> Space:
    # model is Space with fields code and full_name
    return Space.get_default()


@pytest.fixture
def room(space: Space) -> Room:
    # Room has fields code and FK space
    return Room.get_default()
