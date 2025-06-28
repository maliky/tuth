"""Basic crud control on Prerequisite."""

import pytest

from app.academics.models.prerequisite import Prerequisite


@pytest.mark.django_db
def test_prerequisite_crud(curriculum, course_factory, department):
    """Test Create Read Update Delete operation on College Model."""
    # create
    course_a = course_factory(department, "201")
    course_b = course_factory(department, "202")
    prereq = Prerequisite.objects.create(
        curriculum=curriculum,
        course=course_b,
        prerequisite_course=course_a,
    )
    assert Prerequisite.objects.filter(pk=prereq.pk).exists()

    # read
    fetched = Prerequisite.objects.get(pk=prereq.pk)
    assert fetched == prereq

    # update
    fetched.prerequisite_course = course_factory(department, "203")
    fetched.save()
    updated = Prerequisite.objects.get(pk=prereq.pk)
    assert updated.prerequisite_course.number == "203"

    # delete
    updated.delete()
    assert not Prerequisite.objects.filter(pk=prereq.pk).exists()
