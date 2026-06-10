"""Finance helpers for course-specific fee setup from the portal."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import TypedDict

from django.db import transaction

from app.academics.models.course import Course
from app.finance.models.fee_stack import CrsFeeStack, FeeStack, FeeStackLine
from app.finance.models.status_types_methods import FeeType
from app.registry.models.registration import Registration

DEFAULT_SPECIAL_COURSE_FEE = Decimal("15.00")


class CourseFeeSetupResultT(TypedDict):
    """Result metadata for a course-specific fee setup."""

    fee_type_code: str
    fee_stack_id: int
    amount: Decimal
    created_stack: bool
    created_line: bool
    created_link: bool


def suggested_registration_fee_amount(registration: Registration) -> Decimal:
    """Return a safe suggested fee for a zero-tuition special registration."""
    if registration.section.fee_total_amount() > Decimal("0.00"):
        return registration.section.fee_total_amount()
    if infer_course_fee_type_code(registration.section.curriculum_course.course) in {
        "entrepreneurship_education_i",
        "entrepreneurship_education_ii",
        "enterpreneurship",
    }:
        return DEFAULT_SPECIAL_COURSE_FEE
    return Decimal("0.00")


def infer_course_fee_type_code(course: Course) -> str:
    """Infer the best fee type for a course-specific setup action."""
    visible_code = (course.short_code or course.code or "").upper().replace(" ", "")
    title = (course.title or "").lower()
    if visible_code == "EEDU302" or _has_education_suffix(title, "ii"):
        return "entrepreneurship_education_ii"
    if visible_code in {"EED301", "EEDU301"} or _has_education_suffix(title, "i"):
        return "entrepreneurship_education_i"
    if "enterpreneurship" in title or "entrepreneurship" in title:
        return "enterpreneurship"
    return "other"


@transaction.atomic
def ensure_course_default_fee(
    *,
    course: Course,
    amount: Decimal,
    fee_type_code: str | None = None,
) -> CourseFeeSetupResultT:
    """Ensure one course-specific fee stack and default fee line exist."""
    clean_amount = _quantize_money(amount)
    fee_type = _fee_type(fee_type_code or infer_course_fee_type_code(course))
    stack_link = _course_stack_link_for_fee_type(course, fee_type)
    created_stack = False
    created_link = False
    if stack_link is None:
        fee_stack, created_stack = FeeStack.objects.get_or_create(
            name=_course_stack_name(course, fee_type)
        )
        stack_link, created_link = CrsFeeStack.objects.get_or_create(
            course=course,
            fee_stack=fee_stack,
        )
    fee_line, created_line = FeeStackLine.objects.get_or_create(
        fee_stack=stack_link.fee_stack,
        fee_type=fee_type,
        effective_from_semester=None,
        defaults={"amount": clean_amount},
    )
    if not created_line and fee_line.amount != clean_amount:
        fee_line.amount = clean_amount
        fee_line.save(update_fields=["amount"])
    _clear_course_fee_stack_cache(course)
    return {
        "fee_type_code": fee_type.code,
        "fee_stack_id": stack_link.fee_stack_id,
        "amount": clean_amount,
        "created_stack": created_stack,
        "created_line": created_line,
        "created_link": created_link,
    }


def _fee_type(code: str) -> FeeType:
    """Return a fee type, bootstrapping defaults if needed."""
    FeeType._populate_attributes_and_db()
    fee_type, _ = FeeType.objects.get_or_create(
        code=code,
        defaults={"label": code.replace("_", " ").title()},
    )
    return fee_type


def _course_stack_link_for_fee_type(
    course: Course, fee_type: FeeType
) -> CrsFeeStack | None:
    """Return an existing course stack link that already owns the fee type."""
    return (
        CrsFeeStack.objects.filter(
            course=course,
            fee_stack__fees__fee_type=fee_type,
        )
        .select_related("fee_stack")
        .first()
    )


def _course_stack_name(course: Course, fee_type: FeeType) -> str:
    """Return a unique readable stack name for a course-specific fee."""
    course_label = course.short_code or course.code or f"course-{course.pk}"
    return f"Course fee - {course_label} - {fee_type.code}"


def _clear_course_fee_stack_cache(course: Course) -> None:
    """Drop stale prefetched fee-stack links after mutating course fee setup."""
    prefetch_cache = getattr(course, "_prefetched_objects_cache", None)
    if prefetch_cache is not None:
        prefetch_cache.pop("course_fee_stacks", None)


def _has_education_suffix(title: str, suffix: str) -> bool:
    """Return True for Entrepreneurship Education-I/II title variants."""
    compact = title.replace(" ", "").replace("_", "-")
    return compact.endswith(f"education-{suffix}") or compact.endswith(
        f"education{suffix}"
    )


def _quantize_money(value: Decimal) -> Decimal:
    """Normalize a decimal amount to two places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = [
    "DEFAULT_SPECIAL_COURSE_FEE",
    "CourseFeeSetupResultT",
    "ensure_course_default_fee",
    "infer_course_fee_type_code",
    "suggested_registration_fee_amount",
]
