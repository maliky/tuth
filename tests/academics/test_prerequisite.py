"""Test module for Academic Prerequisite."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.prerequisite import Prerequisite

pytestmark = pytest.mark.django_db

# ~~~~~~~~~~~~~~~~DB Constraints ~~~~~~~~~~~~~~~~


def test_prerequisite_crud(curriculum, course_factory):
    """Test Create Read Update Delete operation on College Model."""
    # create
    course_a = course_factory("101")
    course_b = course_factory("202")
    course_c = course_factory("303")

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
    assert fetched.prerequisite_course != course_c

    fetched.prerequisite_course = course_c
    fetched.save()

    updated = Prerequisite.objects.get(pk=prereq.pk)
    assert updated.prerequisite_course.number == "303"

    # delete
    updated.delete()
    assert not Prerequisite.objects.filter(pk=updated.pk).exists()
    assert not Prerequisite.objects.filter(pk=prereq.pk).exists()
    assert not Prerequisite.objects.filter(pk=fetched.pk).exists()


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_prerequisite_unique_per_curriculum(course_factory, curriculum):
    """A prerequisite binome (ordered) exists only once as a prerequisite."""

    course_a = course_factory("101")
    course_b = course_factory("202")

    Prerequisite.objects.create(
        curriculum=curriculum, course=course_b, prerequisite_course=course_a
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Prerequisite.objects.create(
                curriculum=curriculum, course=course_b, prerequisite_course=course_a
            )


def test_prerequisite_no_self(course, curriculum):
    """A course cannot be a prerequisite to itself."""

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Prerequisite.objects.create(
                curriculum=curriculum,
                course=course,
                prerequisite_course=course,
            )


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


# ~~~~ need to implement this in code ~~~~

# def test_cyclic_prerequisite_in_curriculum(course_factory, curriculum):
#     """If A prereq of -> B and B -> C, then we should not have C -> A.

#     Probably needs to be implemented in the code.  not done now 28/06/25.
#     """

#     course_a = course_factory("101")
#     course_b = course_factory("202")
#     course_c = course_factory("303")

#     Prerequisite.objects.bulk_create(
#         [
#             Prerequisite(
#                 curriculum=curriculum, course=course_b, prerequisite_course=course_a
#             ),
#             Prerequisite(
#                 curriculum=curriculum, course=course_c, prerequisite_course=course_b
#             ),
#         ]
#     )

#     with pytest.raises(IntegrityError):
#         with transaction.atomic():
#             Prerequisite.objects.create(
#                 curriculum=curriculum, course=course_a, prerequisite_course=course_c
#             )
