"""Tests for finance utility functions."""

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import pytest

from app.academics.models.curriculum_course import CurriCrs
from tests.constants import D9_99


# > Why do we need those 2 DumyDataClass ?
@dataclass
class DummyCreditHours:
    """Lightweight credit-hours stand-in for tuition_for tests."""

    code: int


@dataclass
class DummyCurriCrs:
    """Minimal curriculum course object used for tuition_for tests."""

    credit_hours: DummyCreditHours

    def tuition_for(self) -> Decimal:
        """Reuse the real CurriCrs logic for testing the rate."""
        return CurriCrs.tuition_for(cast(CurriCrs, self))


@pytest.mark.parametrize("hours", [0, 1, 3])
def test_tuition_for_uses_rate(monkeypatch, hours):
    """tuition_for() should multiply hours by the rate."""
    rate = D9_99
    # Monkeypatch sets the module-level rate without altering global settings.
    monkeypatch.setattr(
        "app.academics.models.curriculum_course.TUITION_RATE_PER_CREDIT",
        rate,
    )

    dummy = DummyCurriCrs(credit_hours=DummyCreditHours(code=hours))
    curriculum_course = cast(CurriCrs, dummy)
    assert curriculum_course.tuition_for() == Decimal(hours) * rate
