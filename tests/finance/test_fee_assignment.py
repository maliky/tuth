"""Tests for semester fee-stack auto-assignment helpers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from django.test import override_settings

from app.finance.fee_assignment import attach_sem_fee_stacks
from app.finance.models.fee_stack import FeeStack, FeeStackLine
from app.finance.models.invoice import CrsInvoice
from app.finance.models.status_types_methods import (
    FeeType,
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _ensure_finance_payment_dfts() -> None:
    """Create lookup rows required by parent invoice foreign keys."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


@override_settings(
    FINANCE_DEFAULT_SEMESTER_FEE_STACK_NAMES=["Registration Base"],
    FINANCE_OPTIONAL_SEMESTER_FEE_STACK_NAMES=["Dormitory Fee"],
)
def test_attach_sem_fee_stacks_is_idempotent(
    curriculum_course_factory,
    sem_factory,
    student,
) -> None:
    """Default and optional stack attachments should be repeatable and stable."""
    curriculum_course = curriculum_course_factory("881", "CURR_FEES")
    semester = sem_factory(1, datetime(2026, 1, 1))
    set_primary_std_curri_enroll(student, curriculum_course.curriculum)
    student.last_enrolled_semester = semester
    student.save(update_fields=["last_enrolled_semester"])

    tuition = curriculum_course.tuition_for()
    course_invoice = CrsInvoice.objects.create(
        curriculum_course=curriculum_course,
        student=student,
        semester=semester,
        initial_amount_due=tuition,
        balance=tuition,
    )
    parent_invoice = course_invoice.student_semester_invoice
    assert parent_invoice is not None

    default_stack = FeeStack.objects.create(name="Registration Base")
    optional_stack = FeeStack.objects.create(name="Dormitory Fee")
    manual_stack = FeeStack.objects.create(name="Manual Extra")

    reg_fee_type = _fee_type("registration", "Registration")
    dorm_fee_type = _fee_type("dormitory", "Dormitory")
    other_fee_type = _fee_type("other", "Other")
    FeeStackLine.objects.create(
        fee_stack=default_stack,
        fee_type=reg_fee_type,
        amount=Decimal("12.00"),
        effective_from_semester=None,
    )
    FeeStackLine.objects.create(
        fee_stack=optional_stack,
        fee_type=dorm_fee_type,
        amount=Decimal("33.00"),
        effective_from_semester=None,
    )
    FeeStackLine.objects.create(
        fee_stack=manual_stack,
        fee_type=other_fee_type,
        amount=Decimal("9.00"),
        effective_from_semester=None,
    )

    parent_invoice.fee_stacks.add(manual_stack)

    first_run = attach_sem_fee_stacks(
        student=student,
        semester=semester,
        optional_stack_ids={optional_stack.id, 999_999},
    )
    parent_invoice.refresh_from_db()
    assert first_run == {"added": 2, "removed_optional": 0, "ignored_optional": 1}
    assert set(parent_invoice.fee_stacks.values_list("id", flat=True)) == {
        manual_stack.id,
        default_stack.id,
        optional_stack.id,
    }

    second_run = attach_sem_fee_stacks(
        student=student,
        semester=semester,
        optional_stack_ids={optional_stack.id, 999_999},
    )
    parent_invoice.refresh_from_db()
    assert second_run == {"added": 0, "removed_optional": 0, "ignored_optional": 1}
    assert set(parent_invoice.fee_stacks.values_list("id", flat=True)) == {
        manual_stack.id,
        default_stack.id,
        optional_stack.id,
    }

    third_run = attach_sem_fee_stacks(
        student=student,
        semester=semester,
        optional_stack_ids=set(),
    )
    parent_invoice.refresh_from_db()
    assert third_run == {"added": 0, "removed_optional": 1, "ignored_optional": 0}
    assert set(parent_invoice.fee_stacks.values_list("id", flat=True)) == {
        manual_stack.id,
        default_stack.id,
    }
