"""Test Section.has_available_seats method."""

import pytest


@pytest.mark.django_db
def test_has_available_seats_true(section_factory):
    section = section_factory(1)
    assert section.has_available_seats()


@pytest.mark.django_db
def test_has_available_seats_false(section_factory):
    section = section_factory(1)
    section.current_registrations = section.max_seats
    assert not section.has_available_seats()
