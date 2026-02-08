"""Tests for create_states finance defaults."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command

from app.finance.models.fee_stack import FeeStack, FeeStackLine
from app.finance.models.status_types_methods import FeeType, Payer

pytestmark = pytest.mark.django_db


def test_create_states_seeds_payers_and_default_fee_stacks() -> None:
    """create_states should seed payer rows and default zero-amount fee stacks."""
    call_command("create_states", verbosity=0)

    payer_codes = set(Payer.objects.values_list("code", flat=True))
    assert {"student", "gov", "scholarship", "other", "mixed"}.issubset(payer_codes)

    # Running twice should keep one baseline line per fee type/stack.
    call_command("create_states", verbosity=0)

    for fee_type in FeeType.objects.all():
        stack_name = fee_type.label or fee_type.code
        fee_stack = FeeStack.objects.filter(name=stack_name).first()
        assert fee_stack is not None
        baseline_lines = FeeStackLine.objects.filter(
            fee_stack=fee_stack,
            fee_type=fee_type,
            effective_from_semester__isnull=True,
        )
        assert baseline_lines.count() == 1
        baseline_line = baseline_lines.first()
        assert baseline_line is not None
        assert baseline_line.amount == Decimal("0.00")
