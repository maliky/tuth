import pytest
from app.registry.models.class_roster import ClassRoster


@pytest.mark.django_db
def test_classroster_crud(section_factory):
    """CRUD operations for ClassRoster."""
    section = section_factory(1)
    roster = ClassRoster.objects.create(section=section)
    assert ClassRoster.objects.filter(pk=roster.pk).exists()

    fetched = ClassRoster.objects.get(pk=roster.pk)
    assert fetched == roster

    fetched.last_updated = fetched.last_updated
    fetched.save()
    updated = ClassRoster.objects.get(pk=roster.pk)
    assert updated

    updated.delete()
    assert not ClassRoster.objects.filter(pk=roster.pk).exists()
