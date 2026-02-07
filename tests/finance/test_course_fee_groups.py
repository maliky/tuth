"""Tests for semester-effective grouped course fees."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.finance.models.course_fee import CourseFee, CourseFeeGroup, CourseFeeGroupFee
from app.finance.models.course_fee import CurriculumCourseFee
from app.finance.models.status_types_methods import FeeType


pytestmark = [pytest.mark.django_db]


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_group_fee_is_not_applied_retroactively(
    curriculum_course_factory,
    semester_factory,
):
    """Group fee starts at effective semester and not before."""
    curriculum_course = curriculum_course_factory("301", "CURR_FEE_RETRO")
    semester_old = semester_factory(1, datetime(2024, 9, 1))
    semester_new = semester_factory(1, datetime(2025, 9, 1))

    group = CourseFeeGroup.objects.create(name="Science Labs")
    group.courses.add(curriculum_course.course)
    CourseFeeGroupFee.objects.create(
        course_fee_group=group,
        fee_type=_fee_type("lab", "Laboratory"),
        amount=Decimal("15.00"),
        effective_from_semester=semester_new,
    )

    assert curriculum_course.total_fee(semester_old) == curriculum_course.tuition_for()
    assert curriculum_course.total_fee(semester_new) == (
        curriculum_course.tuition_for() + Decimal("15.00")
    )


def test_group_fees_are_stackable_and_curriculum_fee_stacks(
    curriculum_course_factory,
    semester_factory,
):
    """Multiple groups and curriculum fees stack for a semester."""
    curriculum_course = curriculum_course_factory("302", "CURR_FEE_STACK")
    semester_one = semester_factory(1, datetime(2024, 9, 1))
    semester_two = semester_factory(1, datetime(2025, 9, 1))

    group_lab = CourseFeeGroup.objects.create(name="Lab Group")
    group_lab.courses.add(curriculum_course.course)
    CourseFeeGroupFee.objects.create(
        course_fee_group=group_lab,
        fee_type=_fee_type("lab", "Laboratory"),
        amount=Decimal("10.00"),
        effective_from_semester=semester_one,
    )

    group_reg = CourseFeeGroup.objects.create(name="Reg Group")
    group_reg.courses.add(curriculum_course.course)
    CourseFeeGroupFee.objects.create(
        course_fee_group=group_reg,
        fee_type=_fee_type("registration", "Registration"),
        amount=Decimal("5.00"),
        effective_from_semester=semester_one,
    )

    CurriculumCourseFee.objects.create(
        curriculum_course=curriculum_course,
        semester=semester_two,
        fee_type=_fee_type("lab", "Laboratory"),
        amount=Decimal("7.00"),
    )

    assert curriculum_course.total_fee(semester_one) == (
        curriculum_course.tuition_for() + Decimal("15.00")
    )
    assert curriculum_course.total_fee(semester_two) == (
        curriculum_course.tuition_for() + Decimal("22.00")
    )


def test_legacy_course_fee_fallback_keeps_semester_specific_override(
    curriculum_course_factory,
    semester_factory,
):
    """Legacy CourseFee rows still work when no fee group is attached."""
    curriculum_course = curriculum_course_factory("303", "CURR_FEE_LEGACY")
    semester_one = semester_factory(1, datetime(2024, 9, 1))
    semester_two = semester_factory(1, datetime(2025, 9, 1))
    fee_type = _fee_type("technology", "Technology")

    CourseFee.objects.create(
        course=curriculum_course.course,
        semester=None,
        fee_type=fee_type,
        amount=Decimal("4.00"),
    )
    CourseFee.objects.create(
        course=curriculum_course.course,
        semester=semester_two,
        fee_type=fee_type,
        amount=Decimal("6.00"),
    )

    assert curriculum_course.total_fee(semester_one) == (
        curriculum_course.tuition_for() + Decimal("4.00")
    )
    assert curriculum_course.total_fee(semester_two) == (
        curriculum_course.tuition_for() + Decimal("6.00")
    )


def test_group_fee_overrides_matching_legacy_fee_type(
    curriculum_course_factory,
    semester_factory,
):
    """Group fee overrides same legacy fee type and keeps other legacy fees."""
    curriculum_course = curriculum_course_factory("304", "CURR_FEE_MIXED")
    semester_one = semester_factory(1, datetime(2024, 9, 1))
    lab_fee_type = _fee_type("lab", "Laboratory")
    tech_fee_type = _fee_type("technology", "Technology")

    CourseFee.objects.create(
        course=curriculum_course.course,
        semester=None,
        fee_type=lab_fee_type,
        amount=Decimal("3.00"),
    )
    CourseFee.objects.create(
        course=curriculum_course.course,
        semester=None,
        fee_type=tech_fee_type,
        amount=Decimal("4.00"),
    )

    group = CourseFeeGroup.objects.create(name="Mixed Group")
    group.courses.add(curriculum_course.course)
    CourseFeeGroupFee.objects.create(
        course_fee_group=group,
        fee_type=lab_fee_type,
        amount=Decimal("10.00"),
        effective_from_semester=semester_one,
    )

    assert curriculum_course.total_fee(semester_one) == (
        curriculum_course.tuition_for() + Decimal("14.00")
    )
