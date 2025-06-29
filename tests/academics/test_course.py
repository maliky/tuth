"""Tests the Course model."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.course import Course

pytestmark = pytest.mark.django_db


def test_course_crud(department):
    """Test the Course CRUD operations."""

    # create
    course = Course.objects.create(
        department=department, number="101", title="Intro Course to Testing in Python"
    )
    assert Course.objects.filter(pk=course.pk).exists()

    # read
    fetched = Course.objects.get(pk=course.pk)
    assert fetched == course

    # update
    assert fetched.title != "Introduction"

    fetched.title = "Introduction"
    fetched.save()
    updated = Course.objects.get(pk=course.pk)
    assert updated.title == "Introduction"

    # delete
    updated.delete()
    assert not Course.objects.filter(pk=course.pk).exists()
    assert not Course.objects.filter(pk=updated.pk).exists()
    assert not Course.objects.filter(pk=fetched.pk).exists()


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_course_number_per_department(department):
    """In a department a course number should be unique."""

    Course.objects.create(department=department, number="101")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Course.objects.create(department=department, number="101")
