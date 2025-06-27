import pytest

from app.academics.models.prerequisite import Prerequisite


@pytest.mark.django_db
def test_prerequisite_crud(curriculum, course_factory):
    # create
    course_a = course_factory("201", "A")
    course_b = course_factory("202", "B")
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
    fetched.prerequisite_course = course_factory("203", "C")
    fetched.save()
    updated = Prerequisite.objects.get(pk=prereq.pk)
    assert updated.prerequisite_course.number == "203"

    # delete
    updated.delete()
    assert not Prerequisite.objects.filter(pk=prereq.pk).exists()

