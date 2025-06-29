"""Tests for curriculum the academic curriculum model."""

import pytest

from app.academics.models.curriculum import Curriculum

# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


@pytest.mark.django_db
def test_curriculum_crud(college):
    """Test Create Read, Update and Delete a Curriculum."""

    # create
    curriculum = Curriculum.objects.create(
        short_name="BSCM",
        long_name="Computer Management",
        college=college,
    )
    assert Curriculum.objects.filter(pk=curriculum.pk).exists()

    # read
    fetched = Curriculum.objects.get(pk=curriculum.pk)
    assert fetched == curriculum

    # update
    assert fetched.long_name != "Computer Management Updated"

    fetched.long_name = "Computer Management Updated"
    fetched.save()
    updated = Curriculum.objects.get(pk=curriculum.pk)
    assert updated.long_name == "Computer Management Updated"

    # delete
    updated.delete()

    assert not Curriculum.objects.filter(pk=curriculum.pk).exists()
    assert not Curriculum.objects.filter(pk=updated.pk).exists()
    assert not Curriculum.objects.filter(pk=fetched.pk).exists()
