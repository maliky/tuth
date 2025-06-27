import pytest
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_section_crud(section_factory):
    """CRUD operations for Section."""
    section = section_factory(1)
    assert Section.objects.filter(pk=section.pk).exists()

    fetched = Section.objects.get(pk=section.pk)
    assert fetched == section

    fetched.number = 2
    fetched.save()
    updated = Section.objects.get(pk=section.pk)
    assert updated.number == 2

    updated.delete()
    assert not Section.objects.filter(pk=section.pk).exists()
