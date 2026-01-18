"""Tests for finance utility functions."""

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import pytest

from app.academics.models.course import CurriculumCourse
from app.finance.utils import tuition_for


# > Why do we need those 2 DumyDataClass ?
@dataclass
class DummyCreditHours:
    """Lightweight credit-hours stand-in for tuition_for tests."""

    code: int


@dataclass
class DummyCurriculumCourse:
    """Minimal curriculum course object used for tuition_for tests."""

    credit_hours: DummyCreditHours


@pytest.mark.parametrize("hours", [0, 1, 3])
def test_tuition_for_uses_rate(monkeypatch, hours):
    """tuition_for() should multiply hours by the rate."""
    rate = Decimal("9.99")
    monkeypatch.setattr("app.finance.utils.TUITION_RATE_PER_CREDIT", rate)

    dummy = DummyCurriculumCourse(credit_hours=DummyCreditHours(code=hours))
    curriculum_course = cast(CurriculumCourse, dummy)
    assert tuition_for(curriculum_course) == Decimal(hours) * rate
