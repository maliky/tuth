"""Tests for CRUD of Courses model."""

import pytest

from app.academics.models.course import Course


@pytest.mark.django_db
def test_course_crud(course_factory, department_factory):
    """Test the Course CRUD operations."""

    # create
    dept = department_factory()
    course = course_factory(dep, "901", title="Intro")
    assert Course.objects.filter(pk=course.pk).exists()

    # read
    fetched = Course.objects.get(pk=course.pk)
    assert fetched == course

    # update
    fetched.title = "Introduction"
    fetched.save()
    updated = Course.objects.get(pk=course.pk)
    assert updated.title == "Introduction"

    # delete
    updated.delete()
    assert not Course.objects.filter(pk=course.pk).exists()
