"""Test for the program model of academics."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.program import Program

pytestmark = pytest.mark.django_db


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_program_unique_course_per_curriculum(program):
    """In a program binomes (course, curriculum) should be unique.

    I can have a course A in several curriculum
    and a curriculm C can have serveral courses,
    but only one line of course A curriculum C should be in program.
    """

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Program.objects.create(
                curriculum=program.curriculum, course=program.course
            )
