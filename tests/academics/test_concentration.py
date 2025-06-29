"""Tests for the Academic Concentration model."""

import pytest

from app.academics.models.concentration import Concentration


@pytest.mark.django_db
def test_concentration_crud(curriculum):
    """Test Create Read Update Delete operation on Concentration Model."""
    # create
    concentration = Concentration.objects.create(
        name="Statistics",
        curriculum=curriculum,
    )
    assert Concentration.objects.filter(pk=concentration.pk).exists()

    # read
    fetched = Concentration.objects.get(pk=concentration.pk)
    assert fetched == concentration

    # update
    assert fetched.name != "Math Stats"

    fetched.name = "Math Stats"
    fetched.save()
    updated = Concentration.objects.get(pk=concentration.pk)
    assert updated.name == "Math Stats"

    # delete
    updated.delete()
    assert not Concentration.objects.filter(pk=updated.pk).exists()
    assert not Concentration.objects.filter(pk=fetched.pk).exists()
    assert not Concentration.objects.filter(pk=concentration.pk).exists()
