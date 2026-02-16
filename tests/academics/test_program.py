"""Test for the curriculum_course model of academics."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.curriculum_course import CurriCourse

pytestmark = pytest.mark.django_db


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_curriculum_course_unique_crs_per_curri(curriculum_course):
    """In a curriculum_course binomes (course, curriculum) should be unique.

    I can have a course A in several curriculum
    and a curriculm C can have serveral courses,
    but only one line of course A curriculum C should be in curriculum_course.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CurriCourse.objects.create(
                curriculum=curriculum_course.curriculum, course=curriculum_course.course
            )
