"""Tests for course admin fee stack bulk action."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

import pytest
from django.contrib import messages
from django.test import RequestFactory

from app.academics.admin.actions import attach_fee_stacks
from app.academics.models.course import Course
from app.finance.models.fee_stack import CourseFeeStack, FeeStack, FeeStackLine
from app.finance.models.status_types_methods import FeeType


pytestmark = pytest.mark.django_db


MessageT: TypeAlias = tuple[str, int]


class DummyAdmin:
    """Simple admin stub that captures action feedback messages."""

    def __init__(self) -> None:
        self.messages: list[MessageT] = []

    def message_user(self, request, message, level=messages.INFO) -> None:
        """Store user-facing action messages for assertions."""
        self.messages.append((str(message), int(level)))


def _fee_type(code: str, label: str) -> FeeType:
    """Return an existing or newly created fee type."""
    fee_type, _ = FeeType.objects.get_or_create(code=code, defaults={"label": label})
    return fee_type


def test_attach_fee_stacks_action_attaches_multiple_stacks_to_courses(
    course_factory,
    semester_factory,
) -> None:
    """Bulk action should attach selected stacks to selected courses."""
    course_one = course_factory("601")
    course_two = course_factory("602")
    semester = semester_factory(1, datetime(2024, 9, 1))
    lab_fee_type = _fee_type("lab", "Laboratory")
    reg_fee_type = _fee_type("registration", "Registration")

    first_stack = FeeStack.objects.create(name="Action Lab")
    second_stack = FeeStack.objects.create(name="Action Reg")
    FeeStackLine.objects.create(
        fee_stack=first_stack,
        fee_type=lab_fee_type,
        amount=Decimal("10.00"),
    )
    FeeStackLine.objects.create(
        fee_stack=second_stack,
        fee_type=reg_fee_type,
        amount=Decimal("5.00"),
    )

    request_factory = RequestFactory()
    request = request_factory.post(
        "/admin/academics/course/",
        data={
            "apply": "yes",
            "_selected_action": [str(course_one.pk), str(course_two.pk)],
            "fee_stacks": [str(first_stack.pk), str(second_stack.pk)],
            "effective_from_semester": str(semester.pk),
        },
    )
    queryset = Course.objects.filter(pk__in=[course_one.pk, course_two.pk])
    model_admin = DummyAdmin()

    response = attach_fee_stacks(model_admin, request, queryset)

    assert response.status_code == 302
    assert CourseFeeStack.objects.filter(
        course=course_one,
        fee_stack=first_stack,
    ).exists()
    assert CourseFeeStack.objects.filter(
        course=course_one,
        fee_stack=second_stack,
    ).exists()
    assert CourseFeeStack.objects.filter(
        course=course_two,
        fee_stack=first_stack,
    ).exists()
    assert CourseFeeStack.objects.filter(
        course=course_two,
        fee_stack=second_stack,
    ).exists()
    assert CourseFeeStack.objects.filter(
        course=course_one,
        fee_stack=first_stack,
        effective_from_semester=semester,
    ).exists()
    assert any(
        "Attached 4 course/stack link(s)." in msg for msg, _ in model_admin.messages
    )


def test_attach_fee_stacks_action_skips_existing_and_invalid_links(
    course_factory,
    semester_factory,
) -> None:
    """Bulk action should skip existing and overlap-invalid attachments."""
    course = course_factory("603")
    semester = semester_factory(1, datetime(2024, 9, 1))
    lab_fee_type = _fee_type("lab", "Laboratory")
    reg_fee_type = _fee_type("registration", "Registration")

    existing_stack = FeeStack.objects.create(name="Existing Lab")
    conflict_stack = FeeStack.objects.create(name="Conflict Lab")
    valid_stack = FeeStack.objects.create(name="Valid Reg")
    FeeStackLine.objects.create(
        fee_stack=existing_stack,
        fee_type=lab_fee_type,
        amount=Decimal("10.00"),
    )
    FeeStackLine.objects.create(
        fee_stack=conflict_stack,
        fee_type=lab_fee_type,
        amount=Decimal("9.00"),
    )
    FeeStackLine.objects.create(
        fee_stack=valid_stack,
        fee_type=reg_fee_type,
        amount=Decimal("5.00"),
    )
    CourseFeeStack.objects.create(
        course=course,
        fee_stack=existing_stack,
        effective_from_semester=semester,
    )

    request_factory = RequestFactory()
    request = request_factory.post(
        "/admin/academics/course/",
        data={
            "apply": "yes",
            "_selected_action": [str(course.pk)],
            "fee_stacks": [
                str(existing_stack.pk),
                str(conflict_stack.pk),
                str(valid_stack.pk),
            ],
            "effective_from_semester": str(semester.pk),
        },
    )
    queryset = Course.objects.filter(pk=course.pk)
    model_admin = DummyAdmin()

    response = attach_fee_stacks(model_admin, request, queryset)

    assert response.status_code == 302
    assert CourseFeeStack.objects.filter(course=course).count() == 2
    assert CourseFeeStack.objects.filter(course=course, fee_stack=valid_stack).exists()
    assert any(
        "Skipped 1 existing course/stack link(s)." in msg
        for msg, _ in model_admin.messages
    )
    assert any(
        "Skipped 1 link(s) because fee types would duplicate on a course." in msg
        for msg, _ in model_admin.messages
    )
