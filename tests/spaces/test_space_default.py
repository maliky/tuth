"""Tests for Space.get_default()."""

import pytest

from app.spaces.models.core import Space

pytestmark = pytest.mark.django_db


def test_space_get_default_returns_saved_instance():
    """Calling get_default should return a persisted Space object."""
    space = Space.get_default()
    assert space.pk is not None
    # ensure that retrieving again returns the same record
    same_space = Space.get_default()
    assert same_space.pk == space.pk
