"""Tests for finance utility functions."""

from decimal import Decimal

import pytest

from app.finance.utils import tuition_for


@pytest.mark.parametrize("hours", [0, 1, 3])
def test_tuition_for_uses_rate(monkeypatch, hours):
    """tuition_for() should multiply hours by the rate."""
    rate = Decimal("9.99")
    monkeypatch.setattr("app.finance.utils.TUITION_RATE_PER_CREDIT", rate)

    assert tuition_for(None, hours) == Decimal(hours) * rate
