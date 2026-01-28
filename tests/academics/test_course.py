"""Tests the Course model."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.course import Course

pytestmark = pytest.mark.django_db


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_course_number_per_department(course_factory):
    """In a department a course number should be unique."""
    course = course_factory("101")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Course.objects.create(department=course.department, number="101")


def test_course_get_or_create_respects_fuzzy_flag(department_factory):
    """Fuzzy threshold reuses near-duplicates; default (1.0) creates a new course."""
    dept = department_factory("FUZY")
    base, _ = Course.objects.get_or_create(
        department=dept, number="101", defaults={"title": "Calculus I"}
    )

    reuse, created = Course.objects.get_or_create(
        department=dept,
        number="101A",
        defaults={"title": "Calculus 1"},
        fuzzy_threshold=0.8,
    )
    assert reuse.id == base.id
    assert created is False

    new_course, created_strict = Course.objects.get_or_create(
        department=dept,
        number="101B",
        defaults={"title": "Calculus 1"},
        # default fuzzy_threshold=1.0 => strict
    )
    assert created_strict is True
    assert new_course.id != base.id
