import pytest
from app.spaces.models.core import Space


@pytest.mark.django_db
def test_space_crud():
    """CRUD operations for Space."""
    space = Space.objects.create(code="BLD1", full_name="Building 1")
    assert Space.objects.filter(pk=space.pk).exists()

    fetched = Space.objects.get(pk=space.pk)
    assert fetched == space

    fetched.full_name = "Building 1 Updated"
    fetched.save()
    updated = Space.objects.get(pk=space.pk)
    assert updated.full_name == "Building 1 Updated"

    updated.delete()
    assert not Space.objects.filter(pk=space.pk).exists()
