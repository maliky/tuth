"""Test section autoincrement module."""

import pytest

from app.timetable.models import Section


@pytest.mark.django_db
def test_assigns_1_when_first_section_created(course, semester):
    section = Section.objects.create(course=course, semester=semester, number=None)

    assert section.number == 1


@pytest.mark.django_db
def test_sequential_numbers(course, semester):
    first = Section.objects.create(course=course, semester=semester, number=None)
    second = Section.objects.create(course=course, semester=semester, number=None)

    assert first.number == 1
    assert second.number == 2


@pytest.mark.django_db
def test_updating_existing_section_does_not_change_number(course, semester):
    section = Section.objects.create(course=course, semester=semester, number=None)
    section.schedule = "MWF"
    section.save()
    section.refresh_from_db()

    assert section.number == 1
