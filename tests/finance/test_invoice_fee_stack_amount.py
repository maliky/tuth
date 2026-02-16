"""Tests for invoice amount behavior with fee stack updates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.finance.models.fee_stack import CourseFeeStack, FeeStack, FeeStackLine
from app.finance.models.invoice import CourseInvoice
from app.finance.models.status_types_methods import FeeType
from app.timetable.models.section import Section


pytestmark = pytest.mark.django_db


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_invoice_initial_amount_is_not_changed_by_later_fee_stack_update(
    curri_crs_factory,
    sem_factory,
    student,
) -> None:
    """Invoice stores initial amount and does not retroactively follow fee edits."""
    curriculum_course = curri_crs_factory("701", "CURR_STACK_INVOICE")
    semester_old = sem_factory(1, datetime(2024, 9, 1))
    semester_new = sem_factory(1, datetime(2025, 9, 1))
    section_old = Section.objects.create(
        semester=semester_old,
        curriculum_course=curriculum_course,
        number=1,
    )
    section_new = Section.objects.create(
        semester=semester_new,
        curriculum_course=curriculum_course,
        number=1,
    )

    student.curriculum = curriculum_course.curriculum
    student.save(update_fields=["curriculum"])

    old_stack = FeeStack.objects.create(name="Invoice Stack Old")
    old_fee_line = FeeStackLine.objects.create(
        fee_stack=old_stack,
        fee_type=_fee_type("registration", "Registration"),
        amount=Decimal("10.00"),
        effective_from_semester=None,
    )
    CourseFeeStack.objects.create(course=curriculum_course.course, fee_stack=old_stack)

    initial_due = section_old.fee_total_amount()
    invoice = CourseInvoice.objects.create(
        curriculum_course=section_old.curriculum_course,
        student=student,
        semester=section_old.semester,
        initial_amount_due=initial_due,
        balance=initial_due,
    )

    FeeStackLine.objects.create(
        fee_stack=old_stack,
        fee_type=_fee_type("registration", "Registration"),
        amount=Decimal("18.00"),
        effective_from_semester=semester_new,
    )
    old_fee_line.amount = Decimal("12.00")
    old_fee_line.save(update_fields=["amount"])
    updated_due_old = section_old.fee_total_amount()
    updated_due_new = section_new.fee_total_amount()

    assert updated_due_old > initial_due
    assert updated_due_new > updated_due_old
    invoice.refresh_from_db()
    assert invoice.initial_amount_due == initial_due
    assert invoice.balance == initial_due
