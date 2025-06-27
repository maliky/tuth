import pytest

from app.academics.models.concentration import Concentration


@pytest.mark.django_db
def test_concentration_crud(curriculum):
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
    fetched.name = "Math Stats"
    fetched.save()
    updated = Concentration.objects.get(pk=concentration.pk)
    assert updated.name == "Math Stats"

    # delete
    updated.delete()
    assert not Concentration.objects.filter(pk=concentration.pk).exists()

