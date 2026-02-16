"""Semester fee-stack assignment helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict, TypeAlias

from django.conf import settings

from app.finance.models.fee_stack import FeeStack
from app.finance.models.invoice import StdSemesterInvoice

DEFAULT_SEMESTER_STACKS_SETTING = "FINANCE_DEFAULT_SEMESTER_FEE_STACK_NAMES"
OPTIONAL_SEMESTER_STACKS_SETTING = "FINANCE_OPTIONAL_SEMESTER_FEE_STACK_NAMES"
PRESENTATION_MONEY_QUANT = Decimal("0.01")
MoneyMapT: TypeAlias = dict[int, Decimal]


class FeeAssignmentSummaryT(TypedDict):
    """Result payload for semester fee-stack assignment updates."""

    added: int
    removed_optional: int
    ignored_optional: int


class OptionalFeeStackChoiceT(TypedDict):
    """View payload for one optional fee-stack selector row."""

    id: int
    name: str
    amount: str
    selected: bool


def _normalized_setting_names(setting_name: str) -> list[str]:
    """Return a clean stack-name list from one settings entry."""
    raw_value = getattr(settings, setting_name, [])
    if isinstance(raw_value, str):
        raw_items = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        raw_items = [str(item) for item in raw_value]
    else:
        raw_items = []

    cleaned_names: list[str] = []
    for item in raw_items:
        name = item.strip()
        if not name:
            continue
        if name in cleaned_names:
            continue
        cleaned_names.append(name)
    return cleaned_names


def _stacks_by_configured_names(setting_name: str) -> list[FeeStack]:
    """Return stacks ordered by the configured stack-name list."""
    configured_names = _normalized_setting_names(setting_name)
    if not configured_names:
        return []
    stack_map = {
        stack.name: stack
        for stack in FeeStack.objects.filter(name__in=configured_names).order_by("name")
    }
    return [stack_map[name] for name in configured_names if name in stack_map]


def _stack_amounts_for_sem(
    fee_stacks: list[FeeStack],
    semester,
) -> MoneyMapT:
    """Return semester amounts keyed by fee-stack id."""
    return {
        fee_stack.id: fee_stack.total_amount_for_semester(semester)
        for fee_stack in fee_stacks
    }


def _quantized_amount_label(amount: Decimal) -> str:
    """Return a money amount with two-decimal precision."""
    return f"{amount.quantize(PRESENTATION_MONEY_QUANT):.2f}"


def optional_semester_stack_choices(
    *,
    student,
    semester,
) -> list[OptionalFeeStackChoiceT]:
    """Return optional fee-stack choices with selection and amount details."""
    optional_stacks = _stacks_by_configured_names(OPTIONAL_SEMESTER_STACKS_SETTING)
    if not optional_stacks:
        return []

    stack_amounts = _stack_amounts_for_sem(optional_stacks, semester)
    parent_invoice = StdSemesterInvoice.objects.filter(
        student=student,
        semester=semester,
    ).first()
    selected_optional_ids: set[int] = set()
    optional_stack_ids = {stack.id for stack in optional_stacks}
    if parent_invoice is not None:
        selected_optional_ids = set(
            parent_invoice.fee_stacks.filter(id__in=optional_stack_ids).values_list(
                "id",
                flat=True,
            )
        )

    return [
        {
            "id": fee_stack.id,
            "name": fee_stack.name,
            "amount": _quantized_amount_label(
                stack_amounts.get(fee_stack.id, Decimal("0.00"))
            ),
            "selected": fee_stack.id in selected_optional_ids,
        }
        for fee_stack in optional_stacks
    ]


def attach_semester_fee_stacks(
    *,
    student,
    semester,
    optional_stack_ids: set[int] | None = None,
) -> FeeAssignmentSummaryT:
    """Attach configured default stacks and selected optional stacks idempotently."""
    parent_invoice = StdSemesterInvoice.objects.filter(
        student=student,
        semester=semester,
    ).first()
    if parent_invoice is None:
        return {"added": 0, "removed_optional": 0, "ignored_optional": 0}

    default_stacks = _stacks_by_configured_names(DEFAULT_SEMESTER_STACKS_SETTING)
    default_amounts = _stack_amounts_for_sem(default_stacks, semester)
    default_stack_ids = {
        fee_stack.id
        for fee_stack in default_stacks
        if default_amounts.get(fee_stack.id, Decimal("0.00")) > Decimal("0.00")
    }

    optional_stacks = _stacks_by_configured_names(OPTIONAL_SEMESTER_STACKS_SETTING)
    allowed_optional_ids = {fee_stack.id for fee_stack in optional_stacks}
    selected_optional_ids = (optional_stack_ids or set()).intersection(
        allowed_optional_ids
    )
    ignored_optional_count = len((optional_stack_ids or set()) - allowed_optional_ids)

    target_ids = default_stack_ids.union(selected_optional_ids)
    current_ids = set(parent_invoice.fee_stacks.values_list("id", flat=True))
    to_add_ids = sorted(target_ids - current_ids)

    # Remove only deselected optional stacks; keep manual/admin-only links intact.
    to_remove_optional_ids = sorted(
        (current_ids.intersection(allowed_optional_ids)) - selected_optional_ids
    )

    if to_add_ids:
        parent_invoice.fee_stacks.add(*to_add_ids)
    if to_remove_optional_ids:
        parent_invoice.fee_stacks.remove(*to_remove_optional_ids)

    return {
        "added": len(to_add_ids),
        "removed_optional": len(to_remove_optional_ids),
        "ignored_optional": ignored_optional_count,
    }
