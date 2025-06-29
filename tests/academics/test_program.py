"""Test for the program model of academics."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.program import Program

pytestmark = pytest.mark.django_db


# ~~~~~~~~~~~~~~~~ DB consraints~~~~~~~~~~~~~~~~


def test_program_crud(course, curriculum):

    # create
    program = Program.objects.create(curriculum=curriculum, course=course)
    assert Program.objects.filter(pk=program.pk).exists()

    # read
    fetched = Program.objects.get(pk=program.pk)
    assert fetched == program

    # update
    assert fetched.is_required is True

    fetched.is_required = False
    fetched.save()
    updated = Program.objects.get(pk=program.pk)
    assert updated.is_required is False

    # delete
    updated.delete()
    assert not Program.objects.filter(pk=updated.pk).exists()
    assert not Program.objects.filter(pk=program.pk).exists()
    assert not Program.objects.filter(pk=fetched.pk).exists()


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_program_unique_course_per_curriculum(course, curriculum):
    """In a program  binomes (course, curriculum) should be unique.

    I can have a course A in several curriculum
    and a curriculm C can have serveral courses.
    but only one line of course A curriculum C should be in program.
    """

    Program.objects.create(curriculum=curriculum, course=course)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Program.objects.create(curriculum=curriculum, course=course)
