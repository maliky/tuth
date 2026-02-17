"""Tests for fee stack model invariants."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from app.finance.models.fee_stack import (
    CrsFeeStack,
    FeeStack,
    FeeStackLine,
    resolve_crs_fee_stack_map,
)
from app.finance.models.status_types_methods import FeeType


pytestmark = pytest.mark.django_db


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_fee_stack_line_rejects_duplicate_dft_line() -> None:
    """A fee stack should keep a single default (null effective_from) line per fee type."""
    fee_stack = FeeStack.objects.create(name="Core Fees")
    fee_type = _fee_type("registration", "Registration")
    FeeStackLine.objects.create(
        fee_stack=fee_stack,
        fee_type=fee_type,
        amount=Decimal("10.00"),
        effective_from_semester=None,
    )

    with pytest.raises(ValidationError):
        FeeStackLine.objects.create(
            fee_stack=fee_stack,
            fee_type=fee_type,
            amount=Decimal("12.00"),
            effective_from_semester=None,
        )


def test_fee_stack_line_requires_dft_before_dated_line(sem_factory) -> None:
    """Dated fee lines require an existing default baseline line."""
    fee_stack = FeeStack.objects.create(name="No Baseline")
    fee_type = _fee_type("lab", "Laboratory")
    semester = sem_factory(1, datetime(2024, 9, 1))

    with pytest.raises(ValidationError):
        FeeStackLine.objects.create(
            fee_stack=fee_stack,
            fee_type=fee_type,
            amount=Decimal("15.00"),
            effective_from_semester=semester,
        )


def test_crs_fee_stack_rejects_duplicate_fee_types(crs_factory) -> None:
    """Attaching overlapping fee types from different stacks should fail."""
    course = crs_factory("501")
    fee_type = _fee_type("lab", "Laboratory")

    first_stack = FeeStack.objects.create(name="Science Base")
    second_stack = FeeStack.objects.create(name="Science Special")
    FeeStackLine.objects.create(
        fee_stack=first_stack,
        fee_type=fee_type,
        amount=Decimal("8.00"),
        effective_from_semester=None,
    )
    FeeStackLine.objects.create(
        fee_stack=second_stack,
        fee_type=fee_type,
        amount=Decimal("11.00"),
        effective_from_semester=None,
    )
    CrsFeeStack.objects.create(course=course, fee_stack=first_stack)

    with pytest.raises(ValidationError):
        CrsFeeStack.objects.create(course=course, fee_stack=second_stack)


def test_crs_fee_stack_allows_disjoint_fee_types(crs_factory) -> None:
    """A course can attach multiple stacks when fee types do not overlap."""
    course = crs_factory("502")
    lab_fee_type = _fee_type("lab", "Laboratory")
    reg_fee_type = _fee_type("registration", "Registration")

    first_stack = FeeStack.objects.create(name="Lab Stack")
    second_stack = FeeStack.objects.create(name="Reg Stack")
    FeeStackLine.objects.create(
        fee_stack=first_stack,
        fee_type=lab_fee_type,
        amount=Decimal("8.00"),
        effective_from_semester=None,
    )
    FeeStackLine.objects.create(
        fee_stack=second_stack,
        fee_type=reg_fee_type,
        amount=Decimal("5.00"),
        effective_from_semester=None,
    )

    CrsFeeStack.objects.create(course=course, fee_stack=first_stack)
    CrsFeeStack.objects.create(course=course, fee_stack=second_stack)

    assert CrsFeeStack.objects.filter(course=course).count() == 2


def test_resolve_crs_fee_stack_map_depends_on_sem(
    crs_factory,
    sem_factory,
) -> None:
    """Resolved fee map should use latest fee line effective for the semester."""
    course = crs_factory("503")
    fee_type = _fee_type("registration", "Registration")
    semester_old = sem_factory(1, datetime(2024, 9, 1))
    semester_new = sem_factory(1, datetime(2025, 9, 1))

    stack = FeeStack.objects.create(name="Registration Versioned")
    FeeStackLine.objects.create(
        fee_stack=stack,
        fee_type=fee_type,
        amount=Decimal("10.00"),
        effective_from_semester=None,
    )
    FeeStackLine.objects.create(
        fee_stack=stack,
        fee_type=fee_type,
        amount=Decimal("18.00"),
        effective_from_semester=semester_new,
    )
    CrsFeeStack.objects.create(course=course, fee_stack=stack)

    old_map, _old_labels = resolve_crs_fee_stack_map(course, semester_old)
    new_map, _new_labels = resolve_crs_fee_stack_map(course, semester_new)

    assert old_map["registration"] == Decimal("10.00")
    assert new_map["registration"] == Decimal("18.00")
