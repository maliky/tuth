"""Test Course.level property."""

import pytest

from app.academics.models import Course


@pytest.mark.django_db
def test_course_level_valid(course_factory, college_factory):
    course = course_factory(number="201", college=college_factory())
    assert course.level == "sophomore"


@pytest.mark.django_db
def test_course_level_invalid(course_factory, college_factory):
    course = course_factory(number="999", college=college_factory())
    assert course.level == "other"
