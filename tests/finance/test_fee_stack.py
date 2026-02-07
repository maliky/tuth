"""Tests for fee stack model invariants."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from app.finance.models.fee_stack import CourseFeeStack, FeeStack, FeeStackLine
from app.finance.models.status_types_methods import FeeType


pytestmark = pytest.mark.django_db


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_fee_stack_line_rejects_duplicate_fee_type() -> None:
    """A fee stack should not allow the same fee type twice."""
    fee_stack = FeeStack.objects.create(name="Core Fees")
    fee_type = _fee_type("registration", "Registration")
    FeeStackLine.objects.create(
        fee_stack=fee_stack,
        fee_type=fee_type,
        amount=Decimal("10.00"),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeeStackLine.objects.create(
                fee_stack=fee_stack,
                fee_type=fee_type,
                amount=Decimal("12.00"),
            )


def test_course_fee_stack_rejects_overlapping_fee_types(course_factory) -> None:
    """Attaching overlapping fee types from different stacks should fail."""
    course = course_factory("501")
    fee_type = _fee_type("lab", "Laboratory")

    first_stack = FeeStack.objects.create(name="Science Base")
    second_stack = FeeStack.objects.create(name="Science Special")
    FeeStackLine.objects.create(
        fee_stack=first_stack,
        fee_type=fee_type,
        amount=Decimal("8.00"),
    )
    FeeStackLine.objects.create(
        fee_stack=second_stack,
        fee_type=fee_type,
        amount=Decimal("11.00"),
    )
    CourseFeeStack.objects.create(course=course, fee_stack=first_stack)

    with pytest.raises(ValidationError):
        CourseFeeStack.objects.create(course=course, fee_stack=second_stack)


def test_course_fee_stack_allows_disjoint_fee_types(course_factory) -> None:
    """A course can attach multiple stacks when fee types do not overlap."""
    course = course_factory("502")
    lab_fee_type = _fee_type("lab", "Laboratory")
    reg_fee_type = _fee_type("registration", "Registration")

    first_stack = FeeStack.objects.create(name="Lab Stack")
    second_stack = FeeStack.objects.create(name="Reg Stack")
    FeeStackLine.objects.create(
        fee_stack=first_stack,
        fee_type=lab_fee_type,
        amount=Decimal("8.00"),
    )
    FeeStackLine.objects.create(
        fee_stack=second_stack,
        fee_type=reg_fee_type,
        amount=Decimal("5.00"),
    )

    CourseFeeStack.objects.create(course=course, fee_stack=first_stack)
    CourseFeeStack.objects.create(course=course, fee_stack=second_stack)

    assert CourseFeeStack.objects.filter(course=course).count() == 2
