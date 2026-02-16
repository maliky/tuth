"""Tests for the Academic Concentration model."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from typing import Any, cast
from app.shared.models import CreditHour

from app.academics.models.concentration import (
    Major,
    MajorCurriCourse,
    Minor,
    MinorCurriCourse,
)
from app.academics.models.curriculum_course import CurriCourse

pytestmark = pytest.mark.django_db


def test_major_get_dft_has_curri_crs():
    """Default major should include one curriculum_course."""
    major = Major.get_dft()

    courses = cast(Any, major.curriculum_courses)
    assert courses.count() == 1


def test_minor_get_dft_has_curri_crs():
    """Default minor should include one curriculum_course."""
    minor = Minor.get_dft()

    courses = cast(Any, minor.curriculum_courses)
    assert courses.count() == 1


def test_total_credit_hours_sums_curri_crs(major):
    """total_credit_hours should add all attached curriculum_course credits."""
    pg = CurriCourse.get_unique_dft()
    pg.credit_hours = CreditHour.objects.get(code=4)
    pg.save()
    courses = cast(Any, major.curriculum_courses)
    courses.add(pg)

    total = sum(p.credit_hours_id for p in courses.all())

    assert major.total_credit_hours() == total


def test_major_clean_requires_curri_crs(curri_factory):
    """clean() should fail if no curriculum_course is attached."""
    curri = curri_factory("TEST_CURRI")
    new_major = Major.objects.create(name="NO_PROG", curriculum=curri)

    with pytest.raises(ValidationError):
        new_major.clean()


def test_major_clean_credit_limit_exceeded(major):
    """clean() should detect credit hour overflow."""
    pg = CurriCourse.get_unique_dft()
    pg.credit_hours = CreditHour.objects.get(code=10)
    pg.save()
    courses = cast(Any, major.curriculum_courses)
    courses.add(pg)
    major.max_credit_hours = 5

    with pytest.raises(ValidationError):
        major.clean()


def test_majorcurri_crs_unique_curri_crs_per_major(curri_factory, curri_crs_factory):
    """(major, curriculum_course) pairs must be unique."""
    major = Major.objects.create(name="M_TEST", curriculum=curri_factory("M_TEST_CURRI"))
    curriculum_course = curri_crs_factory()

    MajorCurriCourse.objects.create(major=major, curriculum_course=curriculum_course)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MajorCurriCourse.objects.create(
                major=major, curriculum_course=curriculum_course
            )


def test_minorcurri_crs_unique_curri_crs_per_minor(curri_factory, curri_crs_factory):
    """(minor, curriculum_course) pairs must be unique."""
    minor = Minor.objects.create(
        name="MNR_TEST", curriculum=curri_factory("MNR_TEST_CURRI")
    )
    curriculum_course = curri_crs_factory()

    MinorCurriCourse.objects.create(minor=minor, curriculum_course=curriculum_course)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MinorCurriCourse.objects.create(
                minor=minor, curriculum_course=curriculum_course
            )
