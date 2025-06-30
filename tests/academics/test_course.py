"""Tests the Course model."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.course import Course

pytestmark = pytest.mark.django_db


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_course_number_per_department(department):
    """In a department a course number should be unique."""

    Course.objects.create(department=department, number="101")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Course.objects.create(department=department, number="101")
