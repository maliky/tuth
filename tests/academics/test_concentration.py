"""Tests for the Academic Concentration model."""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from typing import Any, cast
from app.shared.models import CreditHour

from app.academics.models.concentration import (
    Major,
    MajorCurriculumCourse,
    Minor,
    MinorCurriculumCourse,
)
from app.academics.models.course import CurriculumCourse

pytestmark = pytest.mark.django_db


def test_major_get_default_has_curriculum_course():
    """Default major should include one curriculum_course."""
    major = Major.get_default()

    courses = cast(Any, major.curriculum_courses)
    assert courses.count() == 1


def test_minor_get_default_has_curriculum_course():
    """Default minor should include one curriculum_course."""
    minor = Minor.get_default()

    courses = cast(Any, minor.curriculum_courses)
    assert courses.count() == 1


def test_total_credit_hours_sums_curriculum_course(major):
    """total_credit_hours should add all attached curriculum_course credits."""
    pg = CurriculumCourse.get_unique_default()
    pg.credit_hours = CreditHour.objects.get(code=4)
    pg.save()
    courses = cast(Any, major.curriculum_courses)
    courses.add(pg)

    total = sum(p.credit_hours_id for p in courses.all())

    assert major.total_credit_hours() == total


def test_major_clean_requires_curriculum_course(curriculum_factory):
    """clean() should fail if no curriculum_course is attached."""
    curri = curriculum_factory("TEST_CURRI")
    new_major = Major.objects.create(name="NO_PROG", curriculum=curri)

    with pytest.raises(ValidationError):
        new_major.clean()


def test_major_clean_credit_limit_exceeded(major):
    """clean() should detect credit hour overflow."""
    pg = CurriculumCourse.get_unique_default()
    pg.credit_hours = CreditHour.objects.get(code=10)
    pg.save()
    courses = cast(Any, major.curriculum_courses)
    courses.add(pg)
    major.max_credit_hours = 5

    with pytest.raises(ValidationError):
        major.clean()


def test_majorcurriculum_course_unique_curriculum_course_per_major(
    curriculum_factory, curriculum_course_factory
):
    """(major, curriculum_course) pairs must be unique."""
    major = Major.objects.create(
        name="M_TEST", curriculum=curriculum_factory("M_TEST_CURRI")
    )
    curriculum_course = curriculum_course_factory()

    MajorCurriculumCourse.objects.create(major=major, curriculum_course=curriculum_course)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MajorCurriculumCourse.objects.create(
                major=major, curriculum_course=curriculum_course
            )


def test_minorcurriculum_course_unique_curriculum_course_per_minor(
    curriculum_factory, curriculum_course_factory
):
    """(minor, curriculum_course) pairs must be unique."""
    minor = Minor.objects.create(
        name="MNR_TEST", curriculum=curriculum_factory("MNR_TEST_CURRI")
    )
    curriculum_course = curriculum_course_factory()

    MinorCurriculumCourse.objects.create(minor=minor, curriculum_course=curriculum_course)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MinorCurriculumCourse.objects.create(
                minor=minor, curriculum_course=curriculum_course
            )
