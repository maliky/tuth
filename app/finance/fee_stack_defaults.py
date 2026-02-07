"""Default fee-stack seeding helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias

from app.finance.models.fee_stack import FeeStack, FeeStackLine
from app.finance.models.status_types_methods import FeeType

CreatedCountsT: TypeAlias = tuple[int, int]


def ensure_default_fee_stacks_from_fee_types() -> CreatedCountsT:
    """Ensure one default stack/line (amount 0) exists for each fee type."""
    created_stacks = 0
    created_lines = 0
    for fee_type in FeeType.objects.all().order_by("code"):
        stack_name = fee_type.label or fee_type.code
        fee_stack, stack_created = FeeStack.objects.get_or_create(name=stack_name)
        if stack_created:
            created_stacks += 1
        default_line = FeeStackLine.objects.filter(
            fee_stack=fee_stack,
            fee_type=fee_type,
            effective_from_semester__isnull=True,
        ).first()
        if default_line is None:
            FeeStackLine.objects.create(
                fee_stack=fee_stack,
                fee_type=fee_type,
                amount=Decimal("0.00"),
                effective_from_semester=None,
            )
            created_lines += 1
    return created_stacks, created_lines
